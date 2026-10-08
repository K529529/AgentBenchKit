"""Loopback-only, read-only evidence viewer with explicit artifact boundaries."""

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agentbenchkit.analysis.compare import compare
from agentbenchkit.analysis.judge import unavailable_scores
from agentbenchkit.analysis.replay import analyze_sample
from agentbenchkit.storage.index import read_json, resolve_run

PACKAGE = Path(__file__).parent
MAX_RESPONSE = 1_000_000


def artifact_path(directory: Path, relative: str) -> Path:
    parts = relative.replace("\\", "/").split("/")
    if any(part in {"", ".", "..", "work"} for part in parts):
        raise ValueError("invalid artifact path")
    if parts[0] not in {"tasks", "analyses", "judge"} and relative not in {
        "manifest.json",
        "plan.json",
        "summary.json",
        "summary.md",
        "run_state.json",
    }:
        raise ValueError("artifact is not on the allowlist")
    path = directory.joinpath(*parts)
    if any(
        parent.is_symlink() or parent.is_junction()
        for parent in [path, *path.parents]
        if parent != directory.parent
    ):
        raise ValueError("linked artifacts are not served")
    if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError("artifact not found")
    if path.suffix not in {".json", ".jsonl", ".md", ".txt", ".log", ".diff", ".py", ".toml"}:
        raise ValueError("unsupported artifact format")
    if path.stat().st_size > MAX_RESPONSE:
        raise ValueError("artifact exceeds viewer response limit")
    return path


def create_app(root: Path) -> FastAPI:
    root = root.resolve()
    app = FastAPI(title="AgentBenchKit", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE / "templates")
    templates.env.filters["pretty"] = lambda value: json.dumps(value, indent=2, ensure_ascii=False)

    def run_dir(run_id: str) -> Path:
        try:
            return resolve_run(root, run_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None

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

    @app.get("/", response_class=HTMLResponse)
    def runs(request: Request) -> HTMLResponse:
        items = []
        for path in sorted(root.glob("*/manifest.json"), reverse=True)[:200]:
            directory = run_dir(path.parent.name)
            manifest = read_json(path)
            summary_path = directory / "summary.json"
            items.append(
                {
                    "id": directory.name,
                    "manifest": manifest,
                    "summary": read_json(summary_path) if summary_path.exists() else {},
                }
            )
        return render(request, "runs.html", title="评测运行", runs=items)

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def detail(request: Request, run_id: str) -> HTMLResponse:
        directory = run_dir(run_id)
        manifest = read_json(directory / "manifest.json")
        summary_path = directory / "summary.json"
        samples = [read_json(path) for path in sorted(directory.glob("tasks/*/*/sample.json"))]
        analyses = [path.name for path in sorted(directory.glob("analyses/*.json"))]
        return render(
            request,
            "run.html",
            title=run_id,
            run_id=run_id,
            manifest=manifest,
            summary=read_json(summary_path) if summary_path.exists() else {},
            samples=samples,
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
        manifest = read_json(directory / "manifest.json")
        record = read_json(paths[0])
        task = next(task for task in manifest["tasks"] if task["task_id"] == record["task_id"])
        files = []
        for path in sorted(paths[0].parent.rglob("*")):
            if path.is_file():
                relative = path.relative_to(directory).as_posix()
                try:
                    artifact_path(directory, relative)
                except ValueError:
                    continue
                files.append(relative)
        judges = [
            read_json(path)
            for path in directory.glob("judge/*.json")
            if read_json(path).get("sample_id") == sample_id
        ]
        return render(
            request,
            "sample.html",
            title=sample_id,
            run_id=run_id,
            sample=record,
            benchmark=manifest.get("benchmark", "micro_swe"),
            task=task,
            files=files,
            analysis=analyze_sample(directory, paths[0], manifest["harness"]["capabilities"]),
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

    @app.get("/compare", response_class=HTMLResponse)
    def comparison(request: Request, baseline: str, candidate: str) -> HTMLResponse:
        try:
            result = compare(root, baseline, candidate, persist_analysis=False)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return render(request, "compare.html", title="运行对比", comparison=result)

    return app
