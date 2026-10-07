# V0 acceptance evidence

Validation performed on 2026-10-07 (Asia/Shanghai). Artifact run IDs use UTC.

## Local release checks

- PASS: 127 tests, including 7 real Docker boundary tests.
- PASS: Ruff; strict mypy for Windows and Linux targets.
- PASS: source distribution and wheel build; task assets, Viewer files and MIT
  license present in wheel.
- PASS: real Viewer run/sample navigation inspected in the in-app browser;
  ChatGPT smoke status, model/provider, verifier result and observability visible.
- PASS: 375 source/evidence files compared in memory against the actual authorized
  credential values; zero literal matches. No credential values printed.
- PASS: no managed Agent containers remain; real acceptance work directories empty.
- CI: Windows/Ubuntu passed through 3c6ccc9. Release hardening is pushed with a
  fresh CI run; consult the branch checks for the latest commit result.

## Real Agent runs

| Run ID | Agent / conditions | Evidence |
| --- | --- | --- |
| 20261006T203011Z-585f6541 | Nexus 0.2.0, qwen3.8-flash, Docker | 8/8 verifier PASS, 8/8 sample success |
| 20261006T203835Z-bad81bb9 | Initial Codex minimal binary image | 0/2; helper missing; retained failure evidence |
| 20261006T204304Z-993e7d4f | Complete official Codex package, ChatGPT smoke | 2/2 PASS |
| 20261006T205812Z-7ddbff60 | Common ModelSpec, Codex 0.155.1, gpt-6-astra low, isolated config/tmpfs login | 2/2 PASS |
| 20261006T205831Z-a0484cfc | Common ModelSpec, Nexus, explicit API, clamp | 1/1 PASS |

Same Benchmark / Environment / Verifier contracts were used for both Agents.
No Agent source was modified. Subscription smoke is not formal API model evidence.

Real comparison of the final Nexus/Codex runs: clamp=INCONCLUSIVE,
stable_unique=ADDED. It surfaces different tasks, Harnesses, models, native
conditions and authentication modes. `formal_comparable=false`. An improvement
claim would be unsupported. Versioned replay preserves original evidence.

## Boundary coverage

| Boundary | Reproducible coverage |
| --- | --- |
| Completion vs correctness; no-op/reference; new/deleted/renamed files | test_runtime.py, test_verification.py |
| Protected verifier assets, no model credentials, network none | test_docker.py |
| Startup-only retries and all physical executions retained | test_lifecycle.py |
| Timeout/cancel/limited with PASS; planned denominator; unknown pass@k | test_contracts.py, test_execution.py, test_lifecycle.py |
| Cancellation during Docker creation adopts/removes resource | test_lifecycle.py |
| Verifier ERROR and post-verification cleanup isolation | test_verification.py, test_lifecycle.py |
| Runner interruption and stale retry result recovery | test_lifecycle.py |
| Linux fast-child identity capture race | test_execution.py plus Windows/Ubuntu CI |
| Literal secret redaction and in-memory auth injection | test_execution.py, test_codex.py, test_docker.py |
| Shared model mappings; unsupported controls; isolated config homes | test_model_spec.py |
| Missing observability, immutable replay and comparison confounds | test_analysis.py |
| Judge failure, safe HTTP diagnostics, deadline, historical analyses | test_judge.py, test_judge_diagnostics.py |
| Corrupt SQLite file rebuild preserves source evidence | test_storage.py |
| Read-only Viewer, HTML escaping, traversal and size boundaries | test_viewer.py |

## Real Judge acceptance

PASS: full sample request returned HTTP 200 / stop / COMPLETED; all four dimensions
passed strict schema. Original correctness and three historical failed Judge artifacts
were preserved. See [root causes and live evidence](judge-diagnostics.md).
The owner will run an independent acceptance.

## Explicitly not run

- Real Codex explicit API-provider inference (configuration conversion tested).
- Optional public SWE-bench adapter / official leaderboard evaluation.

These limits are documented rather than counted as successful real-model tests.
