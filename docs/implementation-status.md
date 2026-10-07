# Implementation evidence

Contract: architecture-v0.3.1.md. Evidence below distinguishes offline checks from
real Agent/Docker runs. A failed evaluated Agent is not automatically a toolkit failure.

| Phase | Status | Evidence |
| --- | --- | --- |
| 0: contracts/bootstrap | PASS (Windows + Ubuntu CI) | Python 3.12; 57 tests passed; Ruff and strict mypy passed; CLI help works |
| 1: real Nexus vertical slice | PASS | 72 offline tests; real Nexus v0.2.0, qwen3.8-flash, 2/2 independent verifier PASS; see phase-1-evidence.md |
| 2: Docker/fresh verifier | PASS | 77 tests including 5 real Docker checks; real Nexus Docker run 20261006T201551Z-18e0d730: 2/2 PASS |
| 3: lifecycle hardening | PASS | 86 tests including real Docker cancellation; bounded concurrency, startup-only retries, planned denominators, recovery leases, cleanup fault injection |
| 4: benchmark/persistence | PASS | 8 tasks; all no-op FAIL/reference PASS on host and Docker; 100 tests; index rebuild and manifest identity checks |
| 5: second real Agent + ModelSpec | PASS | Codex 2/2 smoke; common typed model contract; Nexus new-config regression 1/1; see phase-5-evidence.md |
| 6: analysis/replay/compare | PASS | 5 focused tests; immutable versioned replay; real Nexus/Codex comparison correctly warns and returns INCONCLUSIVE |
| 7: rubric/optional judge | PASS (controlled + real Judge); owner recheck pending | Four dimensions; isolated HTTP worker deadline; versioned results; Judge failure/replay preserve correctness |
| 8: viewer | PASS | Read-only/XSS/path/size tests; actual browser run/sample pages checked; model/provider and subscription-smoke limits visible |
| 9: public benchmark | OPTIONAL, NOT RUN | |
| 10: release hardening | PASS (local) | 127 tests incl. 7 Docker; wheel assets/license; secret scan; MIT/docs; see acceptance-v0.md and latest branch CI |

## Post-V0 release hardening

Repeated public tool inputs: PASS (19 new cases; 139 passed / 7 Docker skipped).
Existing real Nexus/Codex trajectories replayed without changing evidence or verdicts.
Stagnation deliberately deferred: no complete per-step mutation evidence.
See [trajectory analyzer assessment](trajectory-analyzers.md).


Judge diagnostics: PASS (18 new controlled cases; 157 passed / 7 Docker skipped).
Ruff and strict mypy pass. One synthetic live diagnostic returned parseable JSON;
the historical real-sample cause remains unconfirmed because its exception was
not retained. This was the diagnostics-only stage; subsequent live evidence is below.
See [diagnostics and retest evidence](judge-diagnostics.md).

Judge canonical output schema: PASS (18 additional cases; 175 passed / 7 Docker skipped).
Ruff and strict mypy on Windows/Linux pass. Full live sample Judge acceptance passed:
HTTP 200 / stop / COMPLETED, four strict dimensions, new artifact
`f0f559a29ce744fda95aed0f40842c17.json`; all 23 original files and 3 failed Judge artifacts
unchanged. Owner independent acceptance remains pending. See judge-diagnostics.md.
