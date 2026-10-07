# Phase 4 evidence

micro_swe now contains eight Python tasks: clamp, stable_unique, chunked,
merge_intervals, dotted_get, csv_summary, config_defaults, parse_bool_regression.
They cover bug/API fixes, a refactor, new files, multi-module changes, TOML defaults
and regression-test addition. Each has five protected checks. Every no-op fixture
fails and every reference passes, both locally and in fresh Docker verification.

Full suite with Docker enabled: 100 PASS. Ruff and strict Windows/Linux mypy PASS.
The SQLite rebuild test deletes indexed rows, reconstructs them from filesystem
evidence, and checks query equivalence. Two historical real runs were indexed.
The JSONL reader tolerates an incomplete final record but rejects corruption in
an earlier line and rejects non-increasing sequence numbers.

Manifests record actual reported Agent versions, executable hashes on host,
framework source hash, task/fixture/verifier hashes, task budgets, declared model
configuration, concurrency, retry policy, capability coverage, platform and Docker
image identity/constraints. Unknown tool/sampling details stay null. A binary hash
is not falsely presented as a verified Agent source commit. The pinned Nexus Docker
source commit is available as an image label. Candidate snapshots include a text diff.

A separate eight-task real Nexus Docker run was launched as additional release
acceptance evidence; its eventual result is recorded at final acceptance rather
than assumed here. Passing reference fixtures is not a model capability claim.
