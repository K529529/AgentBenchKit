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
| 7: rubric/optional judge | NOT RUN | |
| 8: viewer | NOT RUN | |
| 9: public benchmark | OPTIONAL, NOT RUN | |
| 10: release hardening | NOT RUN | |
