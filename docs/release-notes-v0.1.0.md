# AgentBenchKit v0.1.0 release candidate

Lightweight Coding Agent Evaluation & Benchmark Infrastructure.
V0 implementation and owner acceptance are complete. This branch is prepared for
human release review; [PR #1](https://github.com/K529529/AgentBenchKit/pull/1) remains Draft.
No merge, tag, GitHub Release, public-visibility change or PyPI publication has been performed.

## Implemented

- Benchmark / Harness / Environment separation; external Nexus and Codex CLI adapters,
  shared typed ModelSpec and isolated native config homes; manifest schema v2 records conditions.
- HostProcess and whole-Agent Docker execution, bounded lifecycle/cancellation,
  startup-only retries, Candidate Freeze and fresh protected verification.
- Eight Python micro_swe tasks, fixed denominators, candidate_pass / sample_success,
  conservative pass@k, coverage/success rates and immutable physical execution evidence.
- Public trajectory analysis, evidence/confidence-based Failure / RCA, repeated-tool
  observations, versioned replay and manifest-first regression comparison.
- Optional four-dimension LLM Judge: strict canonical JSON output, framework-owned
  version metadata, safe diagnostics and separate usage; never rewrites correctness.
- Rebuildable SQLite index and read-only local Web Viewer.
- Developer onboarding: [adding a Harness](adding-a-harness.md), a runnable
  [composition example](../examples/custom_harness.py), and a packaged `py.typed` marker.
  New Agent registration remains source-level; there is no plugin discovery.

## Validated

- Final checks: **175 tests passed / 7 opt-in Docker skipped**, locked dependency sync,
  Ruff, strict Windows/Linux-target mypy, CLI help and all eight no-op/reference checks.
- sdist/wheel build, task/Viewer assets and licenses, package version/MIT,
  README/docs local links, example syntax/types and source/package secret scans.
  Fresh wheel installation passes CLI, benchmark validation and external type checking.
- [Windows / Ubuntu CI](https://github.com/K529529/AgentBenchKit/actions/workflows/ci.yml).
- Real Nexus 8/8; Codex ChatGPT smoke 2/2; shared ModelSpec regressions;
  earlier Docker boundary tests and browser Viewer inspection.
- Real Judge HTTP 200 / stop / COMPLETED, all four dimensions parsed strictly;
  original correctness and previous failed artifacts preserved.
- Owner acceptance complete (project owner confirmation, 2026-10-07).

Existing immutable live evidence is reused during finalization without new model spend.
See [acceptance](acceptance-v0.md) and [implementation status](implementation-status.md).

## Not run / deferred

- Real Codex explicit API-provider inference (translation/rejection paths are tested).
- Public SWE-bench adapter and official leaderboard evaluation.
- Stagnation detection, plugin discovery, distributed execution and hostile-code isolation.

ChatGPT smoke is not formal same-model evidence. Missing observability and costs remain
N/A; comparison may be INCONCLUSIVE. The eight internal tasks are integration evidence,
not a broad capability ranking. See [limitations](limitations.md) and [model contract](model-contract.md).

## License

[MIT](../LICENSE); bundled third-party HTMX license is retained.
