# Benchmark adapters and execution

Discovery, selection and execution are separate operations. `tasks` reads the
bundled pinned catalog; `make-config` writes an explicit plan. Neither pulls images
nor invokes an Agent. `run` is the operation that executes the selected plan.

| CLI name | Catalog | Guide |
| --- | ---: | --- |
| micro_swe | 8 | [V0 acceptance](acceptance-v0.md) |
| featurebench | 100 | [FeatureBench Fast v1.1](featurebench.md) |
| swe-bench-lite | 300 | [SWE-bench Lite](swe-bench-lite.md) |
| aider-polyglot | 225 | [Polyglot single execution](aider-polyglot.md) |

For public benchmarks, execution requires Linux/WSL, Docker, an ext4 output
location, the pinned clean upstream checkouts/data and an inference image with
the external Agent installed. Configure only selected tasks for smoke runs.
`--all-tasks` is useful for discovery/configuration; it is not an acceptance
requirement and is not the default execution selection.

The FeatureBench frozen 16-task selection is available through
`make-config featurebench --evalset examples/evalsets/featurebench-fast-evalset-v1.json`.
Provide `--output` for the resulting JSON. Selection order and fingerprint are
validated. Do not replace tasks based on Agent outcomes.

## Adapter boundary

`BenchmarkAdapter` is the task-specific contract, analogous to a Java interface
implemented by each external benchmark integration. Runtime orchestrates the
lifecycle and phase deadlines; it does not decide which repository, test command
or grading algorithm a benchmark needs.

| Hook | Responsibility |
| --- | --- |
| load_tasks | Offline task discovery/selection with pinned identity and budgets |
| task_manifest | Reproducible task, evaluator, fixture and image identity |
| prepare | Materialize the Agent workspace; return its concrete Environment |
| collect | Freeze the stopped Agent's allowed candidate scope and hashes |
| verify | Use independent trusted inputs and the official evaluator/test semantics |

Register the adapter in `benchmarks/registry.py`. Keep official imports and data
schemas inside its package. Reuse the bounded worker and immutable Git-patch
helpers where appropriate. `LocalTaskSpec` retains micro_swe-only fixture fields;
public tasks use `TaskSpec` metadata rather than fabricated local verifiers.

Verification returns PASS/FAIL only from a completed official outcome. ERROR means
the independent verdict is unavailable. Agent completion, candidate correctness,
physical execution and cleanup are separate. A completed pipeline can honestly
produce a failed candidate. See [implementation status](implementation-status.md)
for exact real runs, limits, token observations and controls.

## Evidence and comparison

Run manifest identifies benchmark and task pins. Per-execution preparation and
environment records identify actual task images; the run-level environment may
be only the Agent version probe image. Frozen candidates and official reports
remain inspectable in the read-only Viewer. Viewer renders adapter-provided
protocol notices without changing grading.

Replay reanalyzes stored evidence without model calls or official test reruns.
Compare checks benchmark, task metadata/protocol, images, model and other run
conditions before interpreting result differences. Cross-benchmark runs are not
formal comparable experiments. No smoke result estimates a full benchmark score.


`prepare()`'s returned Environment is Agent-only. `verify()` receives the outer
caller's Environment as a fallback hint. Each Adapter must construct independent
verification from pristine inputs; Runtime must not silently reuse an Agent
snapshot/image. A contract regression checks these distinct objects.

Compare retains `changed_conditions=["tasks", ...]` for historical readers and
adds `task_condition_changes`. Legacy `expected_changes=("tasks",)` authorizes
membership changes only (alias `tasks.selection`). Shared-task changes need the
specific `tasks.prompt`, `tasks.verifier_hash`, `tasks.fixture_hash`,
`tasks.baseline_revision`, `tasks.timeouts` or `tasks.metadata` selector. Unspecified
changes remain inconclusive. Missing model controls/account-login caveats still
prevent formal comparability; expected changes do not establish causality.

Replay rules-v3/metrics-v2 separates `reported_request_credits`,
`sdk_session_credits`, `observed_account_delta` and deduplicated
`request_billable_flags`. Historical `credits` remains an SDK-session alias.
Unavailable fields are null, while measured zero is retained. Account delta is
before minus after across matching quota buckets, possibly including unrelated
account activity. Request Credits are not actual billed currency. No conversion
or price estimate is performed; raw trajectories are unchanged.
