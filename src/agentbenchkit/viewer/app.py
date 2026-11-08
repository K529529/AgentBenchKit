"""Loopback-only, read-only evidence viewer with explicit artifact boundaries."""

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agentbenchkit.analysis.compare import compare
from agentbenchkit.analysis.judge import unavailable_scores
from agentbenchkit.storage.index import resolve_run
from agentbenchkit.viewer import presentation as view
from agentbenchkit.viewer.analytics import distribution, paired_metrics

PACKAGE = Path(__file__).parent
MAX_RESPONSE = 1_000_000


def artifact_path(directory: Path, relative: str) -> Path:
    path = view.safe_path(directory, relative)
    if path.stat().st_size > MAX_RESPONSE:
        raise ValueError("artifact exceeds viewer response limit")
    return path


def create_app(root: Path, extra_roots: tuple[Path, ...] = ()) -> FastAPI:
    roots = []
    for configured in (root, *extra_roots):
        resolved = configured.resolve()
        if os.name == "nt" and not str(resolved).startswith("\\\\?\\"):
            resolved = Path("\\\\?\\" + str(resolved))
        roots.append(resolved)
    root = roots[0]
    app = FastAPI(title="AgentBenchKit", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE / "templates")
    templates.env.globals["evidence_link"] = view.link
    templates.env.filters["na"] = lambda value: "N/A" if value is None else value
    templates.env.filters["pretty"] = lambda value: json.dumps(value, indent=2, ensure_ascii=False)
    templates.env.filters["preview"] = lambda value: json.dumps(
        value, indent=2, ensure_ascii=False
    )[:12000]

    def run_dir(run_id: str) -> Path:
        matches = []
        for configured in roots:
            try:
                matches.append(resolve_run(configured, run_id))
            except ValueError:
                continue
        if len(matches) != 1:
            raise HTTPException(404, "Run 不存在、越界或多个证据源中 ID 冲突")
        return matches[0]

    def render(request: Request, template: str, **data: Any) -> HTMLResponse:
        response = templates.TemplateResponse(request=request, name=template, context=data)
        if len(response.body) > MAX_RESPONSE:
            raise HTTPException(413, "page exceeds viewer response limit")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.exception_handler(HTTPException)
    async def error_page(request: Request, exc: HTTPException) -> HTMLResponse:
        response = render(
            request,
            "error.html",
            title="证据暂不可用",
            status=exc.status_code,
            detail=str(exc.detail),
        )
        response.status_code = exc.status_code
        return response

    @app.get("/", response_class=HTMLResponse)
    def runs(request: Request, page: int = 1, q: str = "") -> HTMLResponse:
        items = []
        paths = [
            p
            for p in sorted(
                (p for configured in roots for p in configured.glob("*/manifest.json")),
                key=lambda p: p.parent.name,
                reverse=True,
            )
            if q.casefold() in p.parent.name.casefold()
        ]
        total = len(paths)
        pages = max(1, (total + 14) // 15)
        page = min(max(1, page), pages)
        for path in paths[(page - 1) * 15 : page * 15]:
            directory = run_dir(path.parent.name)
            manifest = view.read(directory, "manifest.json")
            if not manifest:
                continue
            items.append(
                {
                    "id": directory.name,
                    "manifest": manifest,
                    "summary": view.read(directory, "summary.json"),
                }
            )
        return render(
            request,
            "runs.html",
            title="评测运行",
            runs=items,
            total=total,
            page=page,
            pages=pages,
            q=q,
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def detail(request: Request, run_id: str) -> HTMLResponse:
        directory = run_dir(run_id)
        manifest = view.read(directory, "manifest.json")
        if not manifest:
            raise HTTPException(503, "运行清单暂不可读，请稍后刷新")
        samples = [
            view.read(directory, path.relative_to(directory).as_posix())
            for path in sorted(directory.glob("tasks/*/*/sample.json"))
        ]
        samples = [s for s in samples if s.get("sample_id") and s.get("task_id")]
        analyses = [path.name for path in sorted(directory.glob("analyses/*.json"))]
        overview = view.run_view(directory, samples, manifest)
        distributions = [
            distribution(samples, key, label, unit, scale)
            for key, label, unit, scale in [
                ("viewer_duration", "Agent 耗时", "秒", 1000),
                ("viewer_tokens", "Total Tokens", "tokens", 1),
                ("viewer_tools", "工具调用", "次", 1),
            ]
        ]
        return render(
            request,
            "run.html",
            title=run_id,
            run_id=run_id,
            manifest=manifest,
            summary=view.read(directory, "summary.json"),
            samples=samples,
            overview=overview,
            distributions=distributions,
            notices=sorted(
                {
                    task.get("metadata", {}).get("evaluation_notice", "")
                    for task in manifest["tasks"]
                }
                - {""}
            ),
            analyses=analyses,
        )

    @app.get("/runs/{run_id}/samples/{sample_id}", response_class=HTMLResponse)
    def sample(request: Request, run_id: str, sample_id: str) -> HTMLResponse:
        directory = run_dir(run_id)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", sample_id):
            raise HTTPException(404)
        paths = [
            path
            for path in directory.glob("tasks/*/*/sample.json")
            if path.parent.name == sample_id
        ]
        if len(paths) != 1:
            raise HTTPException(404, "sample not found")
        manifest = view.read(directory, "manifest.json")
        if not manifest:
            raise HTTPException(503, "运行清单暂不可读，请稍后刷新")
        record = view.read(directory, paths[0].relative_to(directory).as_posix())
        if not record:
            raise HTTPException(503, "样本正在写入、缺失或不可读，请稍后刷新")
        task = next(
            (
                task
                for task in manifest.get("tasks", [])
                if task["task_id"] == record.get("task_id")
            ),
            {"task_id": record.get("task_id", "Unknown"), "prompt": "任务描述缺失"},
        )
        workbench = view.sample_view(directory, paths[0])
        files = workbench["files"]
        judges: list[dict[str, Any]] = []
        return render(
            request,
            "sample.html",
            title=sample_id,
            run_id=run_id,
            sample=record,
            benchmark=manifest.get("benchmark", "micro_swe"),
            task=task,
            files=files,
            workbench=workbench,
            judges=judges,
            rubric=unavailable_scores(),
        )

    @app.get("/runs/{run_id}/artifact", response_class=PlainTextResponse)
    def artifact(run_id: str, path: str) -> PlainTextResponse:
        try:
            target = artifact_path(run_dir(run_id), path)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None
        return PlainTextResponse(
            target.read_text(encoding="utf-8"), headers={"X-Content-Type-Options": "nosniff"}
        )

    @app.get("/runs/{run_id}/samples/{sample_id}/files", response_class=HTMLResponse)
    def sample_files(
        request: Request, run_id: str, sample_id: str, q: str = "", page: int = 1
    ) -> HTMLResponse:
        directory = run_dir(run_id)
        paths = [p for p in directory.glob("tasks/*/*/sample.json") if p.parent.name == sample_id]
        if len(paths) != 1:
            raise HTTPException(404, "sample not found")
        files = [
            f for f in view.file_list(directory, paths[0].parent) if q.casefold() in f.casefold()
        ]
        pages = max(1, (len(files) + 29) // 30)
        page = min(max(page, 1), pages)
        return render(
            request,
            "files.html",
            title="证据目录",
            run_id=run_id,
            sample_id=sample_id,
            files=files[(page - 1) * 30 : page * 30],
            total=len(files),
            pages=pages,
            page=page,
            q=q,
        )

    @app.get("/runs/{run_id}/samples/{sample_id}/file-events")
    def file_events(run_id: str, sample_id: str, file: str) -> RedirectResponse:
        directory = run_dir(run_id)
        paths = [p for p in directory.glob("tasks/*/*/sample.json") if p.parent.name == sample_id]
        if len(paths) != 1:
            raise HTTPException(404, "sample not found")
        data = view.sample_view(directory, paths[0])
        if not data["trajectory"]:
            raise HTTPException(404, "trajectory missing")
        return RedirectResponse(view.link(run_id, data["trajectory"], sample_id, q=file))

    @app.get("/runs/{run_id}/download")
    def download(run_id: str, path: str) -> FileResponse:
        try:
            target = view.safe_path(run_dir(run_id), path)
        except (ValueError, OSError) as exc:
            raise HTTPException(404, str(exc)) from None
        return FileResponse(
            target,
            media_type="text/plain",
            filename=target.name,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @app.get("/runs/{run_id}/evidence", response_class=HTMLResponse)
    def evidence(
        request: Request,
        run_id: str,
        path: str,
        sample: str = "",
        start: int = 1,
        q: str = "",
        kind: str = "",
        tool: str = "",
        call: str = "",
        file: str = "",
        line: int = 0,
        node: str = "",
        event: int = 0,
        text_offset: int = 0,
    ) -> HTMLResponse:
        directory = run_dir(run_id)
        try:
            target = view.safe_path(directory, path)
        except (ValueError, OSError) as exc:
            raise HTTPException(404, str(exc)) from None
        if target.suffix == ".json" or event:
            if target.stat().st_size > view.JSON_LIMIT and not event:
                raise HTTPException(413, "记录较大，请下载原始证据或使用分段阅读器")
            try:
                document: Any = (
                    next((e for n, e in view.events(target) if n == event), None)
                    if event
                    else json.loads(target.read_text(encoding="utf-8"))
                )
            except (ValueError, OSError):
                raise HTTPException(503, "记录正在写入或格式无效，请稍后重试") from None
            if node:
                for part in node.split("/")[1:]:
                    key = part.replace("~1", "/").replace("~0", "~")
                    try:
                        document = (
                            document[int(key)] if isinstance(document, list) else document[key]
                        )
                    except (ValueError, KeyError, IndexError, TypeError):
                        raise HTTPException(404, "字段不存在或记录发生变化") from None
            next_text = None
            if isinstance(document, str):
                text_offset = max(0, text_offset)
                if len(document) > text_offset + 20000:
                    next_text = text_offset + 20000
                document = document[text_offset : text_offset + 20000]
            pairs = (
                list(document.items())
                if isinstance(document, dict)
                else list(enumerate(document))
                if isinstance(document, list)
                else [("内容", document)]
            )
            pairs = [
                (str(k), v)
                for k, v in pairs
                if not q or q.casefold() in (str(k) + json.dumps(v, ensure_ascii=False)).casefold()
            ]
            offset = max(0, start - 1)
            fields = [
                {
                    "name": k,
                    "value": v,
                    "nested": isinstance(v, (dict, list))
                    or (isinstance(v, str) and len(v) > 600 and isinstance(document, (dict, list))),
                    "count": len(v) if isinstance(v, (dict, list, str)) else None,
                    "node": node + "/" + k.replace("~", "~0").replace("/", "~1"),
                }
                for k, v in pairs[offset : offset + 20]
            ]
            return render(
                request,
                "record.html",
                title=target.name,
                run_id=run_id,
                path=path,
                sample_id=sample,
                node=node,
                fields=fields,
                total=len(pairs),
                next_text=next_text,
                text_offset=text_offset,
                start=offset + 1,
                event=event,
                q=q,
                next_start=offset + 21 if len(pairs) > offset + 20 else None,
            )
        start = max(1, start)
        rows: list[dict[str, Any]] = []
        next_start = None
        mode = (
            "timeline"
            if target.suffix == ".jsonl"
            else "diff"
            if target.suffix == ".diff"
            else "log"
        )
        # Resolve exact new-line location in the original patch, never regenerate it.
        if mode == "diff" and line:
            for row in view.diff_rows(target):
                if row["new"] == line and (not file or file == row["file"]):
                    start = max(1, row["line"] - 5)
                    break
        iterator: Any = (
            view.events(target)
            if mode == "timeline"
            else enumerate(view.diff_rows(target), 1)
            if mode == "diff"
            else view.lines(target)
        )
        tools_seen: set[str] = set()
        kinds_seen: set[str] = set()
        response_budget = 0
        for number, item in iterator:
            if mode == "timeline":
                row = view.event_view(number, item)
                tools_seen.add(row["tool"])
                kinds_seen.add(row["type"])
                search = json.dumps(item, ensure_ascii=False)
                matches = (
                    (not kind or row["type"] == kind or bool(row.get(kind)))
                    and (not tool or row["tool"] == tool)
                    and (not call or row["call_id"] == call)
                )
            elif mode == "diff":
                row = item
                search = row["text"]
                matches = not file or file.casefold() in row["file"].casefold()
            else:
                row = {"line": number, "text": str(item).rstrip("\n")}
                search = str(item)
                matches = True
            if number < start or not matches or (q and q.casefold() not in search.casefold()):
                continue
            if len(rows) >= 60 or response_budget > 350_000:
                next_start = number
                break
            if mode == "timeline":
                row["raw"] = json.dumps(item, ensure_ascii=False, indent=2)[:3000]
            if "text" in row and len(row["text"]) > 3000:
                row["text"] = row["text"][:3000] + " …[超长行预览，下载查看完整内容]"
            response_budget += len(json.dumps(row, ensure_ascii=False).encode("utf-8")) * 2
            rows.append(row)
        return render(
            request,
            "evidence.html",
            title=target.name,
            run_id=run_id,
            path=path,
            sample_id=sample,
            mode=mode,
            rows=rows,
            start=start,
            next_start=next_start,
            q=q,
            kind=kind,
            tool=tool,
            call=call,
            file=file,
            line=line,
            tools_seen=sorted(tools_seen - {""}),
            kinds_seen=sorted(kinds_seen),
            size=target.stat().st_size,
        )

    @app.get("/compare", response_class=HTMLResponse)
    def comparison(request: Request, baseline: str, candidate: str) -> HTMLResponse:
        try:
            base_root = run_dir(baseline).parent
            if run_dir(candidate).parent != base_root:
                raise ValueError("跨证据根目录对比暂不支持，请分别查看运行报告")
            result = compare(base_root, baseline, candidate, persist_analysis=False)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        paired = []
        for identifier in (baseline, candidate):
            directory = run_dir(identifier)
            records = [
                view.read(directory, p.relative_to(directory).as_posix())
                for p in directory.glob("tasks/*/*/sample.json")
            ]
            records = [r for r in records if r.get("task_id") and r.get("sample_id")]
            view.run_view(directory, records, view.read(directory, "manifest.json"))
            paired.append(records)
        comparison_metrics = paired_metrics(*paired)
        return render(
            request,
            "compare.html",
            title="运行对比",
            comparison=result,
            comparison_metrics=comparison_metrics,
            baseline_manifest=view.read(run_dir(baseline), "manifest.json"),
            candidate_manifest=view.read(run_dir(candidate), "manifest.json"),
        )

    return app
