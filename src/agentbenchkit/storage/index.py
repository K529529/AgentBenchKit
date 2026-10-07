"""Rebuildable SQLite query index; filesystem evidence remains authoritative."""

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any


def resolve_run(root: Path, run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id):
        raise ValueError("invalid run ID")
    path = root.resolve() / run_id
    if path.is_symlink() or path.is_junction() or path.resolve().parent != root.resolve():
        raise ValueError("run path escapes artifact root")
    if not (path / "manifest.json").is_file():
        raise ValueError("run not found")
    return path


def connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "index.sqlite3", timeout=30)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, created_at TEXT,
                harness TEXT, environment TEXT, summary TEXT NOT NULL, manifest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS samples (run_id TEXT, sample_id TEXT, task_id TEXT,
                result TEXT NOT NULL, PRIMARY KEY(run_id, sample_id));
            CREATE TABLE IF NOT EXISTS executions (run_id TEXT, execution_id TEXT,
                sample_id TEXT, record TEXT NOT NULL, PRIMARY KEY(run_id, execution_id));
            CREATE TABLE IF NOT EXISTS analyses (run_id TEXT, analysis_id TEXT,
                record TEXT NOT NULL, PRIMARY KEY(run_id, analysis_id));
            CREATE TABLE IF NOT EXISTS artifacts (run_id TEXT, path TEXT, size INTEGER,
                PRIMARY KEY(run_id, path));
        """)
    except sqlite3.Error:
        db.close()
        raise
    return db


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def index_run(root: Path, run_id: str) -> None:
    directory = resolve_run(root, run_id)
    manifest = read_json(directory / "manifest.json")
    summary = read_json(directory / "summary.json") if (directory / "summary.json").exists() else {}
    db = connect(root)
    try:
        with db:
            db.execute(
                "INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?)",
                (
                    run_id,
                    manifest["created_at"],
                    manifest["harness"]["name"],
                    manifest["environment"]["provider"],
                    json.dumps(summary),
                    json.dumps(manifest),
                ),
            )
            for table in ("samples", "executions", "analyses", "artifacts"):
                db.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
            for path in directory.glob("tasks/*/*/sample.json"):
                data = read_json(path)
                db.execute(
                    "INSERT INTO samples VALUES(?,?,?,?)",
                    (run_id, data["sample_id"], data["task_id"], json.dumps(data)),
                )
            for path in directory.glob("tasks/*/*/executions/*/execution.json"):
                data = read_json(path)
                db.execute(
                    "INSERT INTO executions VALUES(?,?,?,?)",
                    (run_id, data["physical_execution_id"], data["sample_id"], json.dumps(data)),
                )
            for path in directory.glob("analyses/*.json"):
                data = read_json(path)
                db.execute(
                    "INSERT INTO analyses VALUES(?,?,?)",
                    (run_id, data["analysis_id"], json.dumps(data)),
                )
            for path in directory.rglob("*"):
                relative = path.relative_to(directory)
                if path.is_file() and "work" not in relative.parts and not path.is_symlink():
                    db.execute(
                        "INSERT INTO artifacts VALUES(?,?,?)",
                        (run_id, relative.as_posix(), path.stat().st_size),
                    )
    finally:
        db.close()


def rebuild(root: Path) -> int:
    if any(read_json(path).get("status") == "RUNNING" for path in root.glob("*/run_state.json")):
        raise ValueError("finish or recover active runs before rebuilding the index")
    try:
        db = connect(root)
    except sqlite3.DatabaseError:
        # The index is disposable, but retain the broken file for diagnosis.
        suffix = ".corrupt-" + uuid.uuid4().hex
        for name in ("index.sqlite3", "index.sqlite3-wal", "index.sqlite3-shm"):
            path = root / name
            if path.exists():
                path.rename(root / (name + suffix))
        db = connect(root)
    try:
        with db:
            for table in ("runs", "samples", "executions", "analyses", "artifacts"):
                db.execute(f"DELETE FROM {table}")
    finally:
        db.close()
    count = 0
    for path in sorted(root.glob("*/manifest.json")):
        index_run(root, path.parent.name)
        count += 1
    return count


def list_runs(root: Path) -> list[dict[str, Any]]:
    db = connect(root)
    try:
        rows = db.execute(
            "SELECT run_id, created_at, harness, environment, summary "
            "FROM runs ORDER BY created_at DESC"
        ).fetchall()
        return [
            dict(
                zip(("run_id", "created_at", "harness", "environment", "summary"), row, strict=True)
            )
            for row in rows
        ]
    finally:
        db.close()
