# Implementation and release status

Contract: [architecture-v0.3.1.md](architecture-v0.3.1.md).
A failed evaluated Agent is not automatically a toolkit failure.

## Current v0.1.0 release candidate

- Owner acceptance complete, confirmed by the project owner on 2026-10-07.
- Final local suite: **175 passed / 7 opt-in Docker skipped**; locked sync, Ruff,
  strict Windows/Linux-target mypy (including examples), CLI help and benchmark validation PASS.
- sdist/wheel build and contents, package version 0.1.0 / MIT, local documentation
  links, example syntax/type checks and tracked/archive secret scans PASS. Fresh
  wheel installation also passes CLI, all eight task checks and external type checking.
- Windows/Ubuntu CI checks run on the release-finalization commit; exact HEAD/results
  are linked in [Draft PR #1](https://github.com/K529529/AgentBenchKit/pull/1).
- Existing real evidence: Nexus 8/8, Codex ChatGPT smoke 2/2, shared ModelSpec regressions,
  Docker fresh verification, browser Viewer review, replay/compare and full real Judge COMPLETED.
- Real Judge artifact `f0f559a29ce744fda95aed0f40842c17.json`: HTTP 200 / stop,
  four strict dimensions; original evidence and historical failed Judge artifacts unchanged.
- Repeated-tool observation is implemented; Stagnation is deliberately deferred.
- Real Codex explicit API inference is NOT RUN; public SWE-bench adapter is deferred.
- This phase changes release documentation, an example and typing package metadata only.
  No merge, tag, GitHub Release, visibility change or PyPI publication is authorized here.

See [acceptance evidence](acceptance-v0.md), [Judge evidence](judge-diagnostics.md),
[Harness integration](adding-a-harness.md) and [limitations](limitations.md).

## Historical implementation phases

The early phase counts below describe checks **at that phase**, not current totals.
Physical failures and original artifacts are retained; they are not current release blockers.

| Phase | Status | Evidence |
| --- | --- | --- |
| 0: contracts/bootstrap | PASS (Windows + Ubuntu CI) | Python 3.12; 57 tests passed; Ruff and strict mypy passed; CLI help works |
| 1: real Nexus vertical slice | PASS | 72 offline tests; real Nexus v0.2.0, qwen3.8-flash, 2/2 independent verifier PASS; see phase-1-evidence.md |
| 2: Docker/fresh verifier | PASS | 77 tests including 5 real Docker checks; real Nexus Docker run 20261006T201551Z-18e0d730: 2/2 PASS |
| 3: lifecycle hardening | PASS | 86 tests including real Docker cancellation; bounded concurrency, startup-only retries, planned denominators, recovery leases, cleanup fault injection |
| 4: benchmark/persistence | PASS | 8 tasks; all no-op FAIL/reference PASS on host and Docker; 100 tests; index rebuild and manifest identity checks |
| 5: second real Agent + ModelSpec | PASS | Codex 2/2 smoke; common typed model contract; Nexus new-config regression 1/1; see phase-5-evidence.md |
| 6: analysis/replay/compare | PASS | 5 focused tests; immutable versioned replay; real Nexus/Codex comparison correctly warns and returns INCONCLUSIVE |
| 7: rubric/optional judge | PASS (controlled + real Judge); owner acceptance complete | Four dimensions; isolated HTTP worker deadline; versioned results; Judge failure/replay preserve correctness |
| 8: viewer | PASS | Read-only/XSS/path/size tests; actual browser run/sample pages checked; model/provider and subscription-smoke limits visible |
| 9: public benchmark | OPTIONAL, NOT RUN | |
| 10: release finalization | PASS | Current checks and acceptance below; no frozen evaluation semantics changed |


## Hardening history

- Repeated-tool observations added with 19 regression cases; existing real trajectories
  replayed without changing evidence/verdicts. See [trajectory analysis](trajectory-analyzers.md).
- Safe Judge diagnostics exposed truncation and then a schema mismatch. The old generic
  error record remains intact; it cannot retroactively supply its swallowed exception.
- Canonical Judge output now shares an exact prompt/schema, rejects ambiguous shapes,
  and receives framework-owned versions only after validation. Full live acceptance
  and subsequent owner acceptance passed; see [diagnostics](judge-diagnostics.md).
