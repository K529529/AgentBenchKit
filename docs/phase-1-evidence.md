# Phase 1 evidence

Real run: `20261006T200220Z-d1f5e797` (UTC), host_process, one sample per task.
Nexus v0.2.0 was installed from unmodified commit
`677fc997dcdc2f369fa8d4a667d400de99e35f84` in an ignored local environment.
Model: qwen3.8-flash; the user explicitly authorized the existing configuration
and DASHSCOPE_API_KEY for this small evaluation. Credential values are not recorded.

| Task | Agent | Verifier | Tests | Sample success |
| --- | --- | --- | --- | --- |
| clamp | COMPLETED | PASS | 5 | true |
| stable_unique | COMPLETED | PASS | 5 | true |

The second task requires adding a new file. Both candidates were frozen after
process-tree termination and reconstructed into fresh verification workspaces.
Candidate files and their hashes, physical execution records, public trajectory,
logs, resolved task/model configuration and summaries are under the ignored
`.agentbenchkit/results/20261006T200220Z-d1f5e797` directory. A known-credential
byte scan found zero matches in persisted files; no run work directories remained.

Offline validation: 72 tests, Ruff, strict mypy for Windows and Linux.
These tests cover timeout/cancellation and normal-exit descendants, bounded output,
new/deleted/renamed candidate files, tampering, protected verifier ownership,
missing reports and streamed credential redaction. Controlled harness fixtures
are test doubles and are separate from the real Nexus evidence above.

Scope: trusted host development only. Docker isolation, concurrency, recovery,
additional benchmarks, the second Agent and later analysis/UI phases remain pending.
