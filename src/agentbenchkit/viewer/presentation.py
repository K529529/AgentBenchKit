"""Read-only, bounded presentation adapters. Never invokes replay or verification."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from agentbenchkit.viewer.analytics import numeric

JSON_LIMIT = 8_000_000
LINE_LIMIT = 2_000_000


def safe_path(root: Path, relative: str) -> Path:
    parts = relative.replace("\\", "/").split("/")
    if any(p in {"", ".", "..", "work"} or ":" in p for p in parts):
        raise ValueError("无效或未授权的证据路径")
    if parts[0] not in {"tasks", "analyses", "judge"} and relative not in {
        "manifest.json",
        "plan.json",
        "summary.json",
        "summary.md",
        "run_state.json",
    }:
        raise ValueError("证据不在允许列表")
    target = root.joinpath(*parts)
    for p in [root, *[root.joinpath(*parts[:i]) for i in range(1, len(parts) + 1)]]:
        if p.is_symlink() or p.is_junction():
            raise ValueError("不允许链接或目录联接")
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("证据尚未落盘或不存在")
    if target.suffix not in {".json", ".jsonl", ".md", ".txt", ".log", ".diff", ".py", ".toml"}:
        raise ValueError("不支持此证据格式")
    return target


def read(root: Path, relative: str) -> dict[str, Any]:
    try:
        p = safe_path(root, relative)
        if p.stat().st_size > JSON_LIMIT:
            return {}
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def lines(path: Path) -> Iterator[tuple[int, str]]:
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        number = 0
        while True:
            line = stream.readline(LINE_LIMIT + 1)
            if not line:
                break
            number += 1
            if len(line) > LINE_LIMIT:
                while line and not line.endswith("\n"):
                    line = stream.readline(LINE_LIMIT + 1)
                yield number, "[超大单行，使用原始下载查看]\n"
            else:
                yield number, line


def events(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    for number, line in lines(path):
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError
            yield number, value
        except ValueError:
            yield number, {"type": "unparsed", "notice": "事件截断、格式无效或超过单行限制"}


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def event_data(event: dict[str, Any]) -> dict[str, Any]:
    return mapping(mapping(mapping(event.get("attributes")).get("native")).get("data"))


def content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(content_text(x) for x in value if isinstance(x, (dict, str)))
    if isinstance(value, dict):
        for key in ("text", "content", "output", "message", "delta"):
            if value.get(key):
                return content_text(value[key])
    return ""


def event_view(number: int, event: dict[str, Any]) -> dict[str, Any]:
    native = mapping(mapping(event.get("attributes")).get("native"))
    data = mapping(native.get("data"))
    pi = mapping(native.get("pi"))
    tool = data.get("name") or pi.get("toolName") or ""
    args = data.get("arguments", data.get("arguments_json", pi.get("args")))
    args_text = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    failure = (
        data.get("ok") is False
        or data.get("is_error") is True
        or pi.get("isError") is True
        or data.get("status") == "failed"
        or (isinstance(data.get("exit_code"), int) and data["exit_code"] != 0)
        or event.get("type") in {"error", "unparsed"}
    )
    change = tool in {"apply_patch", "write", "edit", "write_file", "edit_file"}
    test = bool(
        tool in {"bash", "exec_command", "shell", "run_command"}
        and re.search(r"\b(pytest|unittest|jest|vitest|cargo test|npm test)\b", args_text)
    )
    argument = args
    if isinstance(args, str):
        try:
            argument = json.loads(args)
        except ValueError:
            pass
    if isinstance(argument, dict):
        argument_text = "\n".join(f"{key}: {value}" for key, value in argument.items())
    else:
        argument_text = str(argument or "")
    kind = event.get("type", "")
    summary = content_text(pi.get("result")) or content_text(pi.get("message"))
    summary = summary or content_text(data)
    if kind == "tool_call_started":
        summary = argument_text or "调用参数未收集"
    elif kind == "tool_call_finished" and not summary:
        summary = "工具报告失败" if failure else "工具结果已记录"
        if data.get("exit_code") is not None:
            summary += f" · exit code {data['exit_code']}"
    elif kind == "agent_finished":
        summary = (
            f"Agent 终止事件 · Steps {data.get('steps', 'N/A')}"
            f" · Model calls {data.get('model_calls', 'N/A')}"
        )
    if not summary:
        message = mapping(pi.get("message"))
        if message.get("sections") and message.get("role"):
            summary = f"{message['role']} 消息 · 分节内容请打开完整事件查看"
        elif pi.get("type") == "abk_native_archive":
            summary = "原生事件压缩归档 · 原始内容保留在完整证据中"
    if not summary:
        summary = str(event.get("notice") or data.get("model") or native.get("kind") or kind)
    duration = next(
        (
            value
            for value in (event.get("duration_ms"), data.get("duration_ms"), pi.get("durationMs"))
            if numeric(value)
        ),
        None,
    )
    return {
        "line": number,
        "seq": event.get("seq", number),
        "id": event.get("event_id"),
        "type": event.get("type", "Unknown"),
        "time": event.get("timestamp"),
        "tool": tool,
        "step": data.get("step"),
        "call_id": event.get("native_call_id") or data.get("call_id") or pi.get("toolCallId"),
        "args": args_text,
        "duration": duration,
        "failure": failure,
        "change": change,
        "test": test,
        "summary": summary[:1500],
        "raw": event,
    }


def link(run: str, relative: str, sample: str = "", **params: Any) -> str:
    return f"/runs/{run}/evidence?" + urlencode({"path": relative, "sample": sample, **params})


def reference(root: Path, run: str, ref: str, folder: str, sample: str) -> dict[str, Any]:
    name, _, fragment = ref.partition("#")
    for candidate in (name, f"{folder}/{name}"):
        try:
            safe_path(root, candidate)
            return {
                "ref": ref,
                "url": link(run, candidate, sample, q=fragment),
                "path": candidate,
                "reason": "",
            }
        except (ValueError, OSError):
            pass
    return {"ref": ref, "url": "", "reason": "缺失、越界或格式不支持；未访问授权 Run 之外的路径"}


def file_list(root: Path, folder: Path) -> list[str]:
    # Path.walk does not follow symlinks. Prune scratch before traversing it.
    found = []
    for parent, dirs, names in folder.walk():
        dirs[:] = [
            d
            for d in dirs
            if d != "work" and not (parent / d).is_symlink() and not (parent / d).is_junction()
        ]
        for name in names:
            rel = (parent / name).relative_to(root).as_posix()
            try:
                safe_path(root, rel)
                found.append(rel)
            except (ValueError, OSError):
                pass
    return sorted(found)


def exception_summary(path: Path) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    exceptions = []
    for number, text in lines(path):
        match = re.match(r"^([^\s].*?\.py):(\d+):(?: in .*)?\s*$", text)
        pyframe = re.match(r'^\s*File "([^"]+)", line (\d+)', text)
        frame = match or pyframe
        if frame:
            frames = frames[-11:]
            frames.append({"file": frame[1], "line": int(frame[2]), "log_line": number})
        error = re.match(
            r"^(?:E\s+|\s*)([\w.]+(?:Error|Exception)|KeyboardInterrupt|SystemExit):\s*(.*)", text
        )
        if error:
            exceptions.append(
                {
                    "type": error[1],
                    "message": error[2],
                    "log_line": number,
                    "frames": frames[-12:],
                    "location": frames[-1] if frames else None,
                }
            )
            if len(exceptions) >= 30:
                break
    return exceptions


def sample_view(root: Path, path: Path) -> dict[str, Any]:
    run, sample = root.name, path.parent.name
    folder = path.parent.relative_to(root).as_posix()
    record = read(root, f"{folder}/sample.json")
    verifier = read(root, f"{folder}/verifier.json")
    official = mapping(mapping(verifier.get("checks")).get("official_report"))
    files = file_list(root, path.parent)
    executions = [(f, read(root, f)) for f in files if f.endswith("/execution.json")]
    executions.sort(key=lambda pair: pair[1].get("started_at") or "")
    execution = executions[-1][1] if executions else {}
    trajectory = (
        executions[-1][0].replace("execution.json", "trajectory.jsonl") if executions else ""
    )
    saved: dict[str, Any] = {}
    analysis_ref = ""
    for a in sorted(root.glob("analyses/*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        rel = a.relative_to(root).as_posix()
        results = read(root, rel).get("samples", [])
        saved = next((x for x in results if x.get("sample_id") == sample), {})
        if saved:
            analysis_ref = rel
            break
    metrics: dict[str, Any] = {}
    terminal: dict[str, Any] = {}
    observed: Counter[str] = Counter()
    complete = False
    repeats: dict[str, list[int]] = {}
    repeat_labels: dict[str, str] = {}
    repeat_calls: dict[int, str] = {}
    results_by_call: dict[str, list[dict[str, Any]]] = {}
    if trajectory in files:
        broken = False
        for number, event in events(safe_path(root, trajectory)):
            view = event_view(number, event)
            observed["events"] += 1
            observed["tools"] += int(view["type"] == "tool_call_started")
            observed["tool_failures"] += int(
                view["type"] == "tool_call_finished" and view["failure"]
            )
            observed["models"] += int(view["type"] == "model_call_started")
            broken |= view["type"] == "unparsed"
            if view["type"] == "tool_call_started":
                argument = view["tool"] + " " + view["args"]
                key = hashlib.sha256(argument.encode()).hexdigest()
                repeat_labels[key] = argument[:350]
                repeats.setdefault(key, []).append(number)
                if view["call_id"]:
                    repeat_calls[number] = str(view["call_id"])
            if view["type"] == "tool_call_finished" and view["call_id"]:
                results_by_call.setdefault(str(view["call_id"]), []).append(
                    {"line": number, "summary": view["summary"][:250], "failure": view["failure"]}
                )
            if view["type"] == "agent_finished":
                terminal = event_data(event)
                complete = True
        complete = (
            complete
            and not broken
            and not mapping(execution.get("process")).get("output_truncated", False)
        )
    usage = terminal.get("usage") or {}
    metrics.update(
        {
            k: usage.get(k)
            for k in ["input_tokens", "output_tokens", "total_tokens", "cached_input_tokens"]
        }
    )
    # Only sum known input/output for adapters whose input already includes cache reads.
    if metrics["total_tokens"] is None and all(
        isinstance(metrics[k], int) for k in ["input_tokens", "output_tokens"]
    ):
        metrics["total_tokens"] = metrics["input_tokens"] + metrics["output_tokens"]
    metrics.update(
        steps=terminal.get("steps"),
        model_calls=terminal.get("model_calls"),
        tool_calls=observed["tools"] if trajectory in files else None,
        tool_failures=observed["tool_failures"] if trajectory in files else None,
        duration_ms=mapping(execution.get("process")).get("duration_ms"),
        trajectory_complete=complete if trajectory in files else None,
    )
    groups = []
    for name in ["FAIL_TO_PASS", "PASS_TO_PASS"]:
        group = mapping(mapping(official.get("tests_status")).get(name))
        success, failure = group.get("success"), group.get("failure")
        groups.append(
            {
                "name": name,
                "passed": len(success) if isinstance(success, list) else None,
                "failed": len(failure) if isinstance(failure, list) else None,
                "failures": failure if isinstance(failure, list) else [],
            }
        )
    refs = [
        reference(root, run, str(verifier[k]), folder, sample)
        for k in ["stdout_ref", "stderr_ref"]
        if verifier.get(k)
    ]
    logs = [
        f
        for f in files
        if "/verify/" in f and f.endswith(("test_output.txt", "stdout.log", "stderr.log"))
    ]
    logs.extend(ref["path"] for ref in refs if ref.get("path") and ref["path"] not in logs)
    logs.sort(key=lambda f: (not f.endswith("test_output.txt"), f))
    exceptions = []
    for log in logs[:8]:
        for exc in exception_summary(safe_path(root, log)):
            exc["url"] = link(run, log, sample, start=max(1, exc["log_line"] - 12))
            exc["log"] = log
            exceptions.append(exc)
    failure = saved.get("failure") or {}
    rca_refs = [
        reference(root, run, str(x), folder, sample) for x in failure.get("evidence_refs", [])
    ]
    return dict(
        saved_metrics=saved.get("metrics", {}),
        record=record,
        verifier=verifier,
        official=official,
        groups=groups,
        files=files,
        execution=execution,
        executions=executions,
        trajectory=trajectory if trajectory in files else "",
        patch=f"{folder}/patch.diff" if f"{folder}/patch.diff" in files else "",
        metrics=metrics,
        logs=logs,
        exceptions=exceptions,
        refs=refs,
        failure=failure,
        analysis_ref=analysis_ref,
        rca_refs=rca_refs,
        repeats=[
            {
                "args": repeat_labels[k],
                "lines": v,
                "calls": [
                    {
                        "line": n,
                        "id": repeat_calls.get(n),
                        "results": results_by_call.get(repeat_calls.get(n, ""), []),
                    }
                    for n in v
                ],
            }
            for k, v in repeats.items()
            if len(v) > 1
        ],
        repeat_version="repeated-tool-calls-v1 · 展示规则：相同工具与原始参数",
        phase=failure.get("phase") or "Unknown",
    )


def diff_rows(path: Path) -> Iterator[dict[str, Any]]:
    file, old, new = "", None, None
    for number, text in lines(path):
        if text.startswith("diff --git "):
            file, old, new = "", None, None
        if text.startswith(("--- ", "+++ ")):
            name = text[4:].strip().split("\t", 1)[0]
            if name.startswith('"') and name.endswith('"'):
                try:
                    name = json.loads(name)
                except ValueError:
                    pass
            if name != "/dev/null":
                file = (
                    name.removeprefix("b/") if text.startswith("+++ ") else name.removeprefix("a/")
                )
        hunk = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", text)
        if hunk:
            old, new = int(hunk[1]), int(hunk[2])
        kind = "meta"
        left = right = None
        if not text.startswith(("+++", "---")) and old is not None and new is not None:
            if text.startswith("+"):
                kind, right = "added", new
                new += 1
            elif text.startswith("-"):
                kind, left = "removed", old
                old += 1
            elif text.startswith(" "):
                kind, left, right = "context", old, new
                old += 1
                new += 1
        yield {
            "line": number,
            "text": text.rstrip("\n"),
            "file": file,
            "old": left,
            "new": right,
            "kind": kind,
        }


def run_view(root: Path, samples: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    """Small execution records + bounded trajectory tail; no index writes or full-run replay."""
    saved_metrics: dict[str, Any] = {}
    for analysis in sorted(
        root.glob("analyses/*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        items = read(root, analysis.relative_to(root).as_posix()).get("samples") or []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("sample_id"), str):
                metrics = item.get("metrics")
                if isinstance(metrics, dict):
                    saved_metrics.setdefault(item["sample_id"], metrics)
    counts: Counter[str] = Counter()
    durations: list[float] = []
    tokens: list[int] = []
    for sample in samples:
        folder = f"tasks/{sample.get('task_id')}/{sample.get('sample_id')}"
        execution_paths = sorted((root / folder).glob("executions/*/execution.json"))
        records = [read(root, p.relative_to(root).as_posix()) for p in execution_paths]
        records.sort(key=lambda r: r.get("started_at") or "")
        execution = records[-1] if records else {}
        duration = (execution.get("process") or {}).get("duration_ms")
        duration = duration if numeric(duration) else None
        sample["viewer_duration"] = duration
        sample["viewer_tools"] = saved_metrics.get(sample["sample_id"], {}).get("tool_calls")
        usage: dict[str, Any] = {}
        terminal_seen = False
        execution_id = execution.get("physical_execution_id")
        if execution_id:
            rel = f"{folder}/executions/{execution_id}/trajectory.jsonl"
            try:
                trajectory = safe_path(root, rel)
                with trajectory.open("rb") as stream:
                    size = trajectory.stat().st_size
                    stream.seek(max(0, size - LINE_LIMIT))
                    tail = stream.read(LINE_LIMIT).decode("utf-8", errors="replace")
                for text in reversed(tail.splitlines()):
                    try:
                        event = json.loads(text)
                    except ValueError:
                        continue
                    if isinstance(event, dict) and event.get("type") == "agent_finished":
                        terminal_seen = True
                        native = (event.get("attributes") or {}).get("native") or {}
                        usage = (native.get("data") or {}).get("usage") or {}
                        break
            except (ValueError, OSError):
                pass
        total = usage.get("total_tokens")
        if total is None and all(numeric(usage.get(k)) for k in ["input_tokens", "output_tokens"]):
            total = usage["input_tokens"] + usage["output_tokens"]
        total = total if numeric(total) else None
        sample["viewer_tokens"] = total
        sample["viewer_investigate"] = []
        if sample.get("execution_status") == "FINISHED" and sample.get("verifier_status") == "FAIL":
            sample["viewer_investigate"].append("完成但验证失败")
        if sample.get("execution_status") in {"TIMED_OUT", "ERROR", "INTERRUPTED"}:
            sample["viewer_investigate"].append(sample["execution_status"])
        if sample.get("verifier_status") == "ERROR":
            sample["viewer_investigate"].append("Verifier ERROR")
        if sample.get("candidate_pass") is True and sample.get("sample_success") is not True:
            sample["viewer_investigate"].append("候选通过但端到端未成功")
        if total is None:
            sample["viewer_investigate"].append("Usage 缺失")
        if execution_id and not terminal_seen:
            sample["viewer_investigate"].append("未见轨迹结束事件（可能仍在运行或证据不完整）")
        status = sample.get("execution_status")
        counts["completed"] += int(
            status in {"FINISHED", "TIMED_OUT", "ERROR", "CANCELLED", "INTERRUPTED"}
        )
        counts["timeout"] += int(status == "TIMED_OUT")
        counts["execution_error"] += int(status == "ERROR")
        counts["verifier_error"] += int(sample.get("verifier_status") == "ERROR")
        counts["pass"] += int(sample.get("verifier_status") == "PASS")
        counts["fail"] += int(sample.get("verifier_status") == "FAIL")
        if isinstance(total, int):
            tokens.append(total)
        if isinstance(duration, (int, float)):
            durations.append(duration)
    return {
        "counts": counts,
        "tasks": len(manifest.get("tasks", [])),
        "samples": len(samples),
        "tasks_without_results": sum(
            t.get("task_id") not in {s.get("task_id") for s in samples}
            for t in manifest.get("tasks", [])
        ),
        "usage_coverage": len(tokens),
        "tokens": sum(tokens) if tokens else None,
        "duration_ms": sum(durations) if durations else None,
        "duration_coverage": len(durations),
        "state": read(root, "run_state.json").get("status", "Unknown"),
    }
