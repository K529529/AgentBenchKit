# AgentBenchKit V0.3.1 — Frozen Architecture (Final)

> Status: **Frozen — final contract after Codex review**  
> Project: **AgentBenchKit**  
> Positioning: **Lightweight Coding Agent Evaluation & Benchmark Infrastructure**  
> Scope: V0 focuses on Coding Agents only. The system is local-first, single-machine, lightweight, but must provide a trustworthy end-to-end evaluation chain.

---

# 1. Product Goal

AgentBenchKit is not an Agent framework, not a model-serving platform, and not an online observability SaaS.

Its job is to standardize and automate:

```text
Benchmark / Task
      +
Agent Harness
      +
Environment
      ↓
Evaluation Runtime
      ↓
Trajectory / Evidence
      ↓
Independent Verifier
      +
Rubric / Optional LLM Judge
      ↓
Metrics
      ↓
Failure Analysis / RCA
      ↓
Replay / Regression
      ↓
Report / Viewer
```

The core questions are:

```text
1. Did the Agent execute normally under the declared evaluation conditions?
2. Did the frozen candidate actually pass independent verification?
3. If the candidate passed but the Agent violated timeout/budget/execution constraints,
   should the sample count as an end-to-end success?
4. How did the Agent behave?
5. Why did it fail?
6. Is a newer Agent/model/runtime version measurably better under comparable conditions?
```

---

# 2. Frozen V0 Scope

## Must Have

- Coding Agent only
- Lightweight benchmark: `micro_swe`
- Nexus `v0.2.0` as the first real Agent integration
- At least one second real Coding Agent integration for final V0 acceptance, preferably Codex
- Harness-based external integration through existing public CLI / SDK / API
- No modification of evaluated Agent source code as a standard integration requirement
- `host_process` Environment for trusted local development
- Docker Environment as the primary formal evaluation path
- Fresh independent verification environment
- Async bounded concurrency
- Explicit lifecycle and status model
- Explicit Logical Sample / Physical Execution / Model Retry semantics
- Candidate freeze and immutable evidence
- Timeout / cancellation / cleanup
- Append-only JSONL trajectory
- Harness capability declaration
- Deterministic verifier
- Rubric-based evaluation
- Optional LLM-as-a-Judge
- `candidate_pass` and `sample_success` as separate concepts
- Structured metrics with fixed statistical semantics
- Evidence-based failure analysis
- Rule-first RCA
- Resolved Run Manifest
- SQLite query index
- Local artifact store
- Replay
- Regression comparison
- Local Web Viewer
- CI, tests, lint, type checking

## Explicit Non-Goals

- Full SWE-bench
- Distributed worker architecture
- Message queue
- PostgreSQL
- Redis
- Celery
- Kubernetes
- Remote worker pool
- OpenTelemetry Collector
- Phoenix / LangSmith style online observability platform
- Multi-tenant SaaS
- Agentic RL
- Reward model training
- Large React frontend
- Mandatory deep instrumentation inside evaluated Agents
- Host-side Agent loop with all tool calls transparently redirected into Docker
- Strong hostile-Agent credential isolation in V0
- Full checkpoint resume
- Large-scale model leaderboard claims

---

# 3. Frozen Design Principles

1. **Benchmark, Harness and Environment remain decoupled.**
2. **Harness integrates an Agent externally through public CLI / SDK / API whenever possible.**
3. **Evaluated Agent source code must not need modification for standard integration.**
4. **Environment determines where the whole Agent process executes.**
5. **Runtime coordinates lifecycle; Environment owns execution resources; Harness owns Agent protocol adaptation.**
6. **Deterministic verification has priority over LLM judgment.**
7. **Correctness verification must be independent from the Agent workspace.**
8. **Agent completion is not equivalent to candidate correctness.**
9. **Candidate correctness is not equivalent to end-to-end sample success.**
10. **Execution, Agent outcome, verification, analysis and cleanup statuses must remain independent.**
11. **Trajectory is a first-class persisted evaluation artifact, not plain logs.**
12. **Unavailable observability must be represented as unavailable, not zero.**
13. **Failure facts and failure attribution are separate concepts.**
14. **Resolved run conditions must be persisted for auditability and reproducibility.**
15. **Replay must not overwrite historical analysis results.**
16. **Regression comparison must first verify run comparability.**
17. **Infrastructure failures must not silently improve reported Agent scores.**
18. **The project stays lightweight unless a concrete V0 requirement proves heavier infrastructure necessary.**

---

# 4. High-Level Architecture

```text
┌──────────────────────────────────────────────────────┐
│                  CLI / Eval Config                   │
│ Benchmark / Harness / Env / Model / n / k / 并发     │
└─────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│                Evaluation Runtime                    │
│                                                      │
│ Task Loader → Sample Planner → Async Scheduler       │
│                         │                            │
│            lifecycle / timeout / cancel              │
└──────────────┬──────────┴───────────────┬────────────┘
               │                          │
               ▼                          ▼
┌────────────────────────┐    ┌──────────────────────────┐
│ Agent Harness          │    │ Run Environment          │
│                        │    │                          │
│ NexusHarness           │    │ HostProcess              │
│ CodexHarness           │    │ Docker                   │
│ future: others         │    │ clean workspace          │
│ CLI/SDK/API adapter    │    │ resource/network policy  │
└────────────┬───────────┘    └────────────┬─────────────┘
             └───────────────┬─────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Agent Execution │
                    │ multi-turn/tool │
                    │ edit/test loop  │
                    └────────┬────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────┐
│             Candidate Collection + Freeze            │
│ patch / changed files / stdout / stderr / artifacts  │
└─────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│              Fresh Verification Environment          │
│                                                      │
│ baseline fixture + frozen candidate                  │
│ + verifier-owned protected tests                     │
│                  ↓                                   │
│         Deterministic Verifier                       │
└─────────────────────────┬────────────────────────────┘
                          │
                ┌─────────┴───────────┐
                ▼                     ▼
┌───────────────────────┐  ┌───────────────────────────┐
│ Trajectory / Metrics  │  │ Rubric + Optional Judge   │
│ Analyzer              │  │ quality-only evaluation   │
└──────────┬────────────┘  └────────────┬──────────────┘
           └───────────────┬─────────────┘
                           ▼
┌──────────────────────────────────────────────────────┐
│     Facts / Failure Attribution / RCA                │
│ phase / observation / termination / owner / evidence │
└─────────────────────────┬────────────────────────────┘
                          ▼
┌──────────────────────────────────────────────────────┐
│ SQLite Query Index + Immutable Local Artifacts       │
└─────────────────────────┬────────────────────────────┘
                          ▼
            Replay / Regression / Web Viewer
```

---

# 5. Core Domain Model

## 5.1 Run

A `Run` represents one evaluation experiment.

```text
run_id
created_at
benchmark
harness
environment
resolved_manifest
planned_sample_count
status
```

A Run contains Tasks; each Task contains one or more Logical Samples.

---

## 5.2 TaskSpec

One normalized coding task.

Required fields:

```text
task_id
prompt
fixture
baseline_revision
setup
verification
timeouts
tags
metadata
```

Recommended structured fields:

```text
fixture_hash
verifier_version
task_type
resource_requirements
network_policy
rubric
```

`setup` and `verification` must explicitly define:

```text
command form
working directory
shell
timeout
```

Do not use ambiguous free-form command semantics.

---

# 6. Sample / Physical Execution / Model Retry Contract

These concepts are frozen separately.

## 6.1 Logical Sample

One independent Agent generation opportunity.

```text
sample_id
task_id
sample_index
```

A Logical Sample is the unit counted for end-to-end evaluation and pass@k eligibility.

---

## 6.2 Physical Execution

A concrete infrastructure execution record supporting one Logical Sample.

A Logical Sample may have more than one Physical Execution **only for retries that happen before the Agent enters RUNNING**.

Example:

```text
sample-1
├── execution-1: Docker startup failed
└── execution-2: Environment started, Agent ran
```

Every Physical Execution is persisted separately and never overwritten.

---

## 6.3 Model Retry

Retries owned internally by the Agent/model client.

These:

```text
do not create a new Logical Sample
do not create a new AgentBenchKit sample opportunity
```

They should be recorded when observable.

---

## 6.4 Frozen Retry Rule

> Once the Agent enters RUNNING, AgentBenchKit V0 does not automatically restart the entire Agent as a hidden retry.

This prevents `n=1` from silently receiving multiple generation opportunities.

---

# 7. Candidate Correctness vs Sample Success

This section is a frozen statistical contract.

## 7.1 `candidate_pass`

Definition:

```text
candidate_pass = True
```

only when the frozen candidate receives:

```text
verifier_status == PASS
```

It answers:

> If we independently verify the candidate that the Agent left behind, is that candidate correct?

It says nothing about whether the Agent completed under allowed execution conditions.

Values:

```text
True
False
None
```

Mapping:

```text
PASS     → True
FAIL     → False
ERROR    → None
NOT_RUN  → None
```

---

## 7.2 `sample_success`

Definition:

> Whether one planned Logical Sample satisfied the required execution contract and produced a candidate that passed deterministic verification.

`sample_success` is tri-state:

```text
True
False
None
```

The decision order is frozen:

```text
1. If a disqualifying execution-contract violation is already confirmed
   (for example TIMED_OUT, CANCELLED, LIMITED / budget exhausted, or Agent execution FAILED):
       sample_success = False

2. Else if a framework / verifier failure prevents a reliable correctness verdict:
       sample_success = None

3. Else if execution completed normally and verifier_status == PASS:
       sample_success = True

4. Else if reliable evidence proves the sample did not succeed
   (for example normal completion with verifier_status == FAIL):
       sample_success = False

5. Else:
       sample_success = None
```

This ordering is intentional. A later verifier or analysis error does not erase an already-known execution-contract violation.

### Freeze boundary vs cleanup boundary

The following belongs to **execution validity**, not post-run cleanup:

```text
stop Agent/background processes
confirm execution is no longer mutating the workspace
freeze candidate
```

If Agent stop cannot be confirmed and the candidate may still change, the sample is not a trustworthy normal completion and cannot become `sample_success=True`.

The following belongs to **post-verification cleanup**:

```text
remove temporary directory
remove already-stopped container
delete transient files
```

A failure here is recorded in `cleanup_status`, but does **not** retroactively change an already-determined `sample_success`.

Optional analysis / Rubric / Judge failures also never change an already-determined `sample_success`.

If an overall deadline fires, the system records the phase in which it fired and applies the corresponding execution/verification semantics above.

---

## 7.3 Frozen Truth Table

| Execution / Agent state | Verifier | candidate_pass | sample_success | Notes |
|---|---:|---:|---:|---|
| Normal completion | PASS | True | True | Normal successful sample |
| Normal completion | FAIL | False | False | Agent finished but solution wrong |
| TIMED_OUT | PASS | True | False | Candidate may be correct, but end-to-end sample violated budget |
| TIMED_OUT | ERROR / NOT_RUN | None | False | Timeout is already a conclusive execution failure |
| CANCELLED | PASS | True | False | Candidate correctness preserved, sample not successful |
| CANCELLED | ERROR / NOT_RUN | None | False | Cancellation is already a conclusive execution failure |
| LIMITED / budget exhausted | PASS | True | False | Correct candidate after limit does not erase the limit |
| LIMITED / budget exhausted | ERROR / NOT_RUN | None | False | Limit violation is already conclusive |
| Agent FAILED | PASS | True | False | Preserve candidate evidence; execution contract failed |
| Agent FAILED | ERROR / NOT_RUN | None | False | Agent execution failure is already conclusive |
| Normal completion | ERROR | None | None | Verifier failure prevents reliable correctness adjudication |
| Normal completion | NOT_RUN | None | None | No valid verifier verdict exists |
| Startup retry exhausted before Agent runs | NOT_RUN | None | False | Planned sample did not achieve a valid Agent execution |
| Framework internal failure before any conclusive execution failure | NOT_RUN / ERROR | None | None | Framework fault prevents reliable sample adjudication |
| Post-verification cleanup ERROR after successful freeze + verdict | PASS / FAIL | unchanged | unchanged | Cleanup fault is reported separately and does not rewrite sample result |
| Optional Judge / analysis ERROR | PASS / FAIL | unchanged | unchanged | Analysis cannot rewrite deterministic execution/correctness result |

---

# 8. Metric Semantics

## 8.1 `end_to_end_success_rate`

Primary V0 operational success metric.

```text
successful logical samples / planned logical samples
```

where success means:

```text
sample_success == True
```

Infrastructure / timeout / cancellation failures remain in the denominator.

---

## 8.2 `candidate_pass_rate`

Optional descriptive metric.

Definition:

```text
candidate_pass == True
/
samples with verifier_status in {PASS, FAIL}
```

This answers:

> Among samples for which we obtained a valid deterministic verdict, how often was the frozen candidate correct?

It may include:

```text
TIMED_OUT + PASS
CANCELLED + PASS
LIMITED + PASS
```

because it is explicitly about candidate correctness, not end-to-end success.

This metric must always be labeled as conditional on available verifier results.

---

## 8.3 `coverage_rate`

Definition:

```text
samples with verifier_status in {PASS, FAIL}
/
planned logical samples
```

Coverage means:

> We obtained a valid deterministic PASS/FAIL verdict.

Verifier `ERROR` and `NOT_RUN` are not covered.

---

## 8.4 `valid_sample_pass_rate`

To avoid ambiguity, V0 SHOULD NOT use this name in public reports.

Use:

```text
candidate_pass_rate
```

instead.

This removes confusion between "valid sample", "candidate correctness" and "end-to-end success".

---

## 8.5 pass@k

For one task:

```text
n = number of planned independent Logical Samples
k = pass@k parameter
c = number of Logical Samples with sample_success == True
```

When:

```text
n >= k
```

and every planned Logical Sample has a conclusive end-to-end success value:

```text
pass@k = 1 - C(n-c, k) / C(n, k)
```

### Conservative V0 Rule

If any required Logical Sample has:

```text
sample_success == None
```

because of verifier/framework uncertainty, pass@k for that task is:

```text
N/A
```

with an explicit reason.

Do not silently reduce `n`.

---

## 8.6 Task Aggregation

Run-level reports must include:

```text
tasks_planned
tasks_with_valid_pass_at_k
tasks_excluded_from_pass_at_k
samples_planned
samples_successful
samples_with_valid_verdict
```

For task-level pass@k values that are not `N/A`, the run-level aggregate pass@k is the **arithmetic mean across valid tasks**.

Reports must always show:

```text
number of tasks included
number of tasks excluded
exclusion reasons
```

If no task has a valid pass@k value:

```text
aggregate pass@k = N/A
```

For any rate whose denominator is zero, including `candidate_pass_rate` when no sample has a valid PASS/FAIL verifier verdict:

```text
rate = N/A
```

Do not emit `0` for an undefined zero-denominator metric.

---

# 9. Harness Contract

Harness adapts an existing Agent into AgentBenchKit.

```text
Prepared Task
      ↓
Harness
      ↓
Agent CLI / SDK / Public API
      ↓
Agent output + public runtime events
      ↓
Normalized result
```

## Hard Rule

> Adding support for a new Agent means adding or changing AgentBenchKit adapter code, not modifying that Agent's source code.

Examples:

```text
NexusHarness
CodexHarness
MiniSWEHarness
```

---

# 10. Nexus Integration

Target fixed version:

```text
Nexus v0.2.0
```

Static review confirmed tag:

```text
677fc997dcdc2f369fa8d4a667d400de99e35f84
```

Primary public interface:

```text
nexus exec "<task>" --json
```

NexusHarness responsibilities:

```text
prepare isolated Nexus config
inject model config and evaluation credential
launch Nexus
stream stdout/stderr
parse public JSONL events
declare observable capabilities
collect final result
collect candidate changes
stop Agent/background processes
```

Harness does not determine correctness.

Docker installation/execution remains an implementation-phase integration proof, not assumed from static review.

---

# 11. Second Real Agent Integration

V0 final acceptance requires at least one additional real Coding Agent.

Preferred:

```text
Codex
```

Goal:

```text
same Benchmark
same Task
same Environment class
same Verifier
different Harness / Agent
```

No evaluated Agent source modification should be required.

This proves AgentBenchKit is not merely a Nexus-specific evaluation script.

---

# 12. Harness Capability Contract

Different Agents expose different observability depth.

Each Harness declares capabilities.

Example:

```text
final_answer        yes
tool_calls          yes
tool_results        yes
model_usage         yes
model_input         no
model_output        partial
native_call_ids     yes
patch               yes
file_reads          unavailable
```

Rules:

- Unsupported capability → `N/A`
- Observable but zero occurrences → `0`
- Do not infer hidden model or tool events.
- Do not force Agent source modification to obtain deeper tracing.
- Reports must show coverage.

---

# 13. Environment Contract

## 13.1 HostProcessEnvironment

Purpose:

```text
trusted local development
debug
smoke tests
```

Characteristics:

```text
no sandbox isolation
host filesystem/process permissions
no strong CPU/memory isolation guarantee
```

Not the primary formal evaluation environment.

---

## 13.2 DockerEnvironment

Primary formal V0 evaluation path.

Important semantic:

> The whole Agent process runs inside the selected Environment.

For Nexus:

```text
Docker container
   ↓
workspace
   ↓
Nexus runtime
   ↓
Nexus tools / shell commands
```

Not:

```text
Nexus on host
   ↓
tools somehow redirected into Docker
```

V0 Docker capabilities:

```text
fresh container
fresh workspace
CPU limit
memory limit
network policy
command timeout
stdout/stderr capture
container/process cleanup
artifact collection
```

---

# 14. Credential Boundary

V0 does not claim hostile-Agent credential isolation.

Formal policy:

- Only trusted benchmark fixtures in V0.
- Evaluation uses a dedicated low-privilege API key.
- Secrets are injected only at runtime.
- Secrets are never persisted.
- Logs, trajectory and exceptions are redacted.
- Viewer never exposes raw credentials.
- Documentation must explicitly state that an Agent process inside Docker may technically access its own model credential.

Future hardening may use:

```text
credential broker
sidecar model proxy
tool-process environment stripping
separate model / tool execution trust domains
```

These are not V0 blockers.

---

# 15. Independent Verification

This is a core correctness boundary.

The Agent must not control its own final verifier.

Formal lifecycle:

```text
immutable baseline fixture
        ↓
Run Environment
        ↓
Agent modifies candidate workspace
        ↓
stop Agent and background processes
        ↓
freeze candidate changes
        ↓
Fresh Verification Environment
        ↓
restore clean baseline
        ↓
apply frozen candidate
        ↓
inject verifier-owned protected tests/checks
        ↓
execute verifier
        ↓
structured verification result
```

Protected verifier assets must not be writable by the Agent.

---

# 16. Candidate Collection Contract

Candidate collection must support:

```text
modified tracked files
new untracked files
deleted files
renamed files
file mode changes where relevant
```

Do not assume plain `git diff` alone is sufficient.

Binary modifications may be explicitly unsupported in V0 if documented.

Candidate artifacts:

```text
candidate_manifest.json
patch.diff where representable
collected_files/
candidate_hash
```

The frozen candidate hash is used by verifier and Replay.

---

# 17. Micro-SWE

V0 primary internal benchmark:

```text
micro_swe
```

Characteristics:

```text
Python-only
lightweight
small fixtures
deterministic verifier
no huge Docker images
CI-friendly where possible
```

Initial rollout:

```text
2 vertical-slice tasks
↓
expand to 8–15 tasks
```

Task classes:

```text
bug fix
regression-test addition
multi-file change
API behavior fix
refactor
config/dependency fix
```

Each task must have verifier validity evidence:

```text
no-op candidate
→ must fail / not satisfy task

reference correct candidate
→ must pass
```

---

# 18. Optional Public Benchmark Validation

V0 core acceptance does not require running a large public benchmark.

After core V0 works, AgentBenchKit may add a public Benchmark Adapter.

Preferred target:

```text
SWE-bench Lite dev
```

but only:

```text
a small pinned subset, e.g. 1–5 samples
```

is required for external validation.

Purpose:

> Prove that AgentBenchKit can adapt a real public Coding Agent benchmark without requiring full SWE-bench-scale storage or execution.

Full 23-case or 300-case execution is not a V0 requirement.

---

# 19. Status Model

At minimum:

```text
execution_status
agent_outcome
verifier_status
analysis_status
cleanup_status
```

## execution_status

```text
PENDING
PREPARING
RUNNING
COLLECTING
FINISHED
ERROR
TIMED_OUT
CANCELLED
INTERRUPTED
```

## agent_outcome

```text
COMPLETED
FAILED
LIMITED
ABORTED
UNKNOWN
```

## verifier_status

```text
PASS
FAIL
ERROR
NOT_RUN
```

## analysis_status

```text
COMPLETED
PARTIAL
ERROR
NOT_RUN
```

## cleanup_status

```text
COMPLETED
PARTIAL
ERROR
NOT_RUN
```

No single field is allowed to collapse execution, correctness and analysis into one overloaded status.

---

# 20. Attempt Lifecycle and Phase Budgets

Frozen lifecycle:

```text
PREPARE
→ AGENT
→ COLLECT
→ VERIFY
→ ANALYZE
→ CLEANUP
```

Each phase has an explicit budget.

Suggested config:

```text
prepare_timeout_seconds
agent_timeout_seconds
collect_timeout_seconds
verify_timeout_seconds
analysis_timeout_seconds
cleanup_timeout_seconds
```

Also support an optional overall task deadline.

Rules:

- Cancellation must stop process tree / container, not only cancel Python coroutine.
- stdout/stderr must be continuously drained.
- Output is size-bounded.
- Agent must be stopped before candidate freeze.
- Cleanup has an independent deadline.
- Cleanup failure is recorded separately and does not overwrite the original failure.
- Program restart must identify abandoned/running records and mark them `INTERRUPTED`.
- V0 does not require full checkpoint resume.

---

# 21. Minimal Runtime Protection in Phase 1

The first real Nexus vertical slice must already include:

```text
minimal Agent timeout
process termination
stdout/stderr draining
output size limit
basic resolved run snapshot
basic secret redaction
partial evidence preservation
```

Phase 3 may later harden:

```text
systematic cancellation
error injection
orphan recovery
phase-specific timeout policies
cleanup fault handling
```

The first real Agent run must never be unbounded.

---

# 22. Retry Policy

## Before Agent RUNNING

Allowed limited infrastructure retry:

```text
environment startup failure
temporary setup failure
```

Each retry produces a distinct Physical Execution record.

## After Agent RUNNING

Default:

```text
no full-agent automatic restart
```

Model transport retries remain owned by the Agent itself.

Every retry remains auditable.

---

# 23. Trajectory Schema

Storage:

```text
append-only JSONL
```

Required non-null identity fields:

```text
schema_version
event_id
run_id
task_id
sample_id
physical_execution_id
seq
timestamp
source
type
```

Conditionally nullable / optional fields:

```text
status
native_call_id
span_id
parent_span_id
duration_ms
attributes
input_ref
output_ref
```

Rules:

- `seq` monotonically increases within one Physical Execution.
- `native_call_id` is null when not applicable/unobservable.
- `duration_ms` is null for events without a completed duration.
- input/output refs are null when unavailable.
- Null/unavailable is distinct from zero/empty.
- Capability declarations explain expected coverage.

Suggested normalized event types:

```text
agent_started
model_call_started
model_call_finished
tool_call_started
tool_call_finished
command_started
command_finished
patch_observed
test_observed
final_answer
agent_finished
execution_error
```

Do not invent events that cannot be observed reliably.

Raw public Agent events may be retained as redacted artifacts for adapter debugging.

---

# 24. Deterministic Verifier

Primary correctness authority.

Verifier output:

```text
status
exit_code
tests_discovered
tests_executed
tests_passed
tests_failed
tests_skipped
assertions / checks
stdout_ref
stderr_ref
duration_ms
```

Suspicious outcomes must not become PASS:

```text
zero tests discovered
all tests skipped unexpectedly
verification command missing
protected verifier asset missing
```

---

# 25. Rubric Evaluation

Rubric measures quality dimensions that deterministic verification cannot fully capture.

V0 prefers dimension-level output:

```text
test_quality
tool_use_quality
solution_quality
efficiency
```

Avoid double-counting deterministic correctness inside an arbitrary composite quality score unless a specific use case requires it.

Rubric output:

```text
dimension
score
reason
evidence_refs
judge_version
```

---

# 26. LLM-as-a-Judge

LLM Judge is optional.

Inputs:

```text
task
candidate artifacts
selected trajectory evidence
rubric
```

Hard rule:

> Judge failure must never change deterministic verifier PASS/FAIL.

Keep separate:

```text
verifier_status
candidate_pass
sample_success
rubric_scores
judge_status
```

Judge output must be versioned and replayable.

---

# 27. Failure / RCA Model

Do not collapse observation and causality.

Each analysis record:

```text
phase
observations
termination_reason
suspected_owner
confidence
evidence_refs
analysis_version
```

Top-level suspected owners:

```text
AGENT
MODEL
HARNESS
ENVIRONMENT
BENCHMARK
VERIFIER
FRAMEWORK
UNKNOWN
```

Example observations:

```text
NO_MUTATION
TEST_FAILURE
REPEATED_TOOL_CALL
STAGNATION
INVALID_TOOL_CALL
MODEL_API_ERROR
CONTEXT_OVERFLOW
COMMAND_TIMEOUT
RESOURCE_LIMIT
SETUP_FAILURE
VERIFIER_ERROR
```

Observation is evidence, not proof of root cause.

---

# 28. RCA Strategy

V0:

```text
structured rule analysis first
        ↓
optional LLM narrative
```

LLM RCA may summarize:

```text
what happened
where it happened
supporting evidence
most plausible explanation
uncertainty
```

It must not overwrite structured facts.

---

# 29. Resolved Run Manifest

Every Run persists actual resolved experimental conditions after defaults/overrides.

At minimum:

```text
benchmark id/version
task ids
task fixture hashes
baseline revisions
verifier versions

harness id/version
agent version/tag/commit
agent config
enabled tools / skills / MCP where known

model id
provider/base endpoint identity
sampling params
reasoning config
context/output budgets

environment provider
container image digest
OS
shell
CPU/memory limits
network policy

framework version
trajectory schema version
analyzer versions
judge configuration
```

Secrets excluded/redacted.

Definition:

> AgentBenchKit promises experiment-condition reconstruction and auditability, not deterministic remote-model output reproduction.

---

# 30. Storage Model

## Filesystem = Evidence Source

Suggested layout:

```text
results/
└── <run_id>/
    ├── manifest.json
    ├── summary.json
    ├── summary.md
    └── tasks/
        └── <task_id>/
            └── <sample_id>/
                ├── sample.json
                ├── candidate_manifest.json
                ├── candidate/
                ├── verifier.json
                ├── analyses/
                │   └── <analysis_id>.json
                ├── judge/
                │   └── <analysis_id>.json
                └── executions/
                    ├── <physical_execution_id_1>/
                    │   ├── execution.json
                    │   ├── trajectory.jsonl
                    │   ├── stdout.log
                    │   └── stderr.log
                    └── <physical_execution_id_2>/
                        ├── execution.json
                        ├── trajectory.jsonl
                        ├── stdout.log
                        └── stderr.log
```

A later retry must never overwrite earlier physical execution evidence.

Files should use temporary write + atomic replace where appropriate.

JSONL readers tolerate an incomplete final line and mark the trajectory as truncated/incomplete.

---

## SQLite = Query Index + Runtime State

Suggested tables:

```text
runs
tasks
samples
executions
metrics
failures
artifacts
analyses
```

SQLite is not the sole truth for completed evidence.

Completed artifacts must be sufficient to rebuild the index.

---

# 31. Replay

Replay means:

```text
saved immutable evidence
        ↓
new analyzer / classifier / RCA / judge
```

Every analysis run gets:

```text
analysis_id
analysis_version
input_evidence_hash
created_at
output
```

Old analysis remains readable.

V0 Replay supports:

```text
re-run metrics
re-run failure classification
re-run RCA
optional re-run rubric judge
```

Fresh re-verification of historical candidates may be added later.

---

# 32. Regression Compare

Command concept:

```text
agent-bench compare <baseline_run> <candidate_run>
```

Before comparing scores, compare manifests.

Check:

```text
task set
fixture hashes
verifier versions
environment constraints
model config
budgets
concurrency
analyzer versions
```

Expected changed variables may include:

```text
Agent version
model
specific runtime setting
```

Other differences must be surfaced.

Per-task comparison statuses:

```text
IMPROVED
REGRESSED
UNCHANGED
ADDED
REMOVED
INCONCLUSIVE
```

A single stochastic PASS→FAIL transition is reported as observed regression evidence, not proof of stable capability regression.

---

# 33. Web Viewer

Local read-only evaluation viewer.

Stack:

```text
FastAPI
Jinja2
HTMX
minimal JavaScript
```

Bind to localhost by default.

Pages:

```text
Runs
Run Detail
Task / Sample Detail
Trajectory / Evidence Detail
Compare Detail
```

Viewer shows:

```text
resolved manifest
execution status
agent outcome
candidate_pass
sample_success
verifier result
metrics
trajectory coverage
failure facts
RCA
rubric/judge
analysis version
```

Security:

```text
HTML escaping
artifact path allowlist
response size limit
no arbitrary host file browsing
```

---

# 34. CLI

Repository:

```text
AgentBenchKit
```

Python package:

```text
agentbenchkit
```

CLI:

```text
agent-bench
```

Suggested commands:

```text
agent-bench list benchmarks
agent-bench list harnesses
agent-bench list envs

agent-bench run <benchmark> <harness>
  --env docker
  --samples 1
  --concurrency 2

agent-bench view <run-id>

agent-bench replay <run-id>

agent-bench compare <baseline-run> <candidate-run>
```

---

# 35. Technology Stack

```text
Python 3.12+
uv / pyproject.toml
Typer + Rich
Pydantic v2
asyncio
SQLite
Docker
FastAPI
Jinja2
HTMX
pytest + pytest-asyncio
Ruff
mypy
GitHub Actions
OpenAI-compatible API
```

Explicitly excluded from V0:

```text
PostgreSQL
Redis
MQ
Celery
Kubernetes
distributed workers
```

---

# 36. Implementation Strategy — Vertical Slice First

## Phase 0 — Contract Freeze + Bootstrap

Deliver:

```text
project scaffold
core models
status model
sample/success statistical contract
Harness protocol
Environment protocol
Verifier protocol
trajectory schema
resolved manifest schema
CI / lint / type / test baseline
```

Commit:

```text
feat: freeze v0 core contracts
```

---

## Phase 1 — First Real Vertical Slice

Goal:

> One real Nexus task can be evaluated end-to-end safely.

Deliver:

```text
2 micro_swe Python tasks
HostProcessEnvironment
NexusHarness
candidate collection
independent verifier boundary
trajectory JSONL
CLI run
minimal artifact persistence
minimal timeout
process stop
stdout/stderr draining
output size limit
basic resolved manifest
secret redaction
```

Required evidence:

```text
Agent completes but verifier FAILS
Agent completes and verifier PASSES
no-op candidate rejected
reference candidate accepted
new file collection works
```

Commit:

```text
feat: complete first nexus evaluation slice
```

Do not proceed if real Agent integration invalidates core contracts.

---

## Phase 2 — Docker + Fresh Verification

Deliver:

```text
DockerEnvironment
whole Nexus process inside Docker
fresh run workspace
fresh verification environment
resource constraints
network policy
cleanup
```

Required evidence:

```text
Agent cannot overwrite protected verifier assets
fresh verifier reproduces PASS/FAIL
container cleanup confirmed
```

Commit:

```text
feat: add isolated docker evaluation
```

---

## Phase 3 — Runtime Hardening

Deliver:

```text
bounded concurrency
phase budgets
process/container cancellation
systematic output limits
infrastructure retry before Agent start
interrupt detection
orphan cleanup
error injection tests
```

Required evidence:

```text
cancel leaves no running Agent/container
timeout preserves partial evidence
cleanup error does not overwrite original error
```

Commit:

```text
feat: harden evaluation lifecycle
```

---

## Phase 4 — Expand Benchmark + Persistence

Deliver:

```text
8–15 micro_swe Python tasks
fixture validation
full resolved run manifest
SQLite index
artifact recovery/index rebuild
metrics aggregation
candidate_pass/sample_success reporting
```

Commit:

```text
feat: expand micro-swe and persistent run index
```

---

## Phase 5 — Second Agent Integration

Deliver:

```text
CodexHarness or another mature Coding Agent Harness
same micro_swe
same verifier contract
same Environment abstraction
capability declaration
```

Required evidence:

```text
second Agent runs without source modification
same benchmark requires no special verifier rewrite
missing capabilities appear as N/A
```

Commit:

```text
feat: add second coding agent harness
```

---

## Phase 6 — Failure Analysis + Replay + Compare

Deliver:

```text
observations
termination reasons
suspected ownership
confidence
evidence refs
rule-based RCA
analysis versioning
Replay
Regression Compare
comparability checks
```

Commit:

```text
feat: add evidence-based failure and regression analysis
```

---

## Phase 7 — Rubric + Optional Judge

Deliver:

```text
rubric schema
dimension scoring
LLM-as-a-Judge
Judge usage/cost separation
Judge failure isolation
analysis_id versioning
```

Required evidence:

```text
Judge failure does not alter verifier result
historical judge analysis remains readable after replay
```

Commit:

```text
feat: add rubric and llm judge evaluation
```

---

## Phase 8 — Web Viewer

Deliver:

```text
Runs page
Run Detail
Task/Sample Detail
Trajectory view
Verifier evidence
candidate_pass/sample_success
Failure/RCA
Compare view
```

Commit:

```text
feat: add local evaluation viewer
```

---

## Phase 9 — Optional Public Benchmark Adapter

Optional before or after V0 release depending on time.

Preferred:

```text
SWE-bench Lite dev adapter
```

Only a small pinned subset is required.

Commit:

```text
feat: add public benchmark smoke adapter
```

---

## Phase 10 — Hardening + Public Release

Deliver:

```text
end-to-end smoke
secret scan
error-path tests
README
architecture docs
usage examples
limitations
LICENSE
release notes
```

Commit:

```text
chore: prepare agentbenchkit v0.1.0
```

---

# 37. Mandatory Architecture Boundary Tests

Before V0 is considered complete, automated or reproducible evidence must cover:

1. Agent reports success but verifier fails.
2. Agent attempts to modify evaluation-owned verification assets.
3. New untracked file is collected and verified.
4. Deleted/renamed file is represented correctly.
5. Environment startup failure does not become Agent failure.
6. Verifier crash produces `ERROR`, not `FAIL`.
7. Judge failure does not change verifier correctness.
8. Cancellation leaves no active process/container.
9. Timeout preserves partial candidate and trajectory evidence.
10. `TIMED_OUT + PASS` results in `candidate_pass=True` and `sample_success=False`.
11. `CANCELLED + PASS` results in `candidate_pass=True` and `sample_success=False`.
12. `LIMITED + PASS` does not count as normal end-to-end success.
13. pass@k becomes N/A when required sample success is inconclusive.
14. Coverage does not silently exclude verifier/framework uncertainty.
15. Replay creates a new analysis instead of overwriting old analysis.
16. Compare warns when fixture/verifier/environment conditions differ.
17. Unsupported Harness metrics appear as unavailable rather than zero.
18. No-op and reference candidate validation exists for each task class.
19. A broken SQLite index can be rebuilt from completed run artifacts.
20. Multiple startup retries preserve all Physical Execution records.

---

# 38. V0 Acceptance Criteria / Release Gate

This section defines when AgentBenchKit V0 is actually "done".

## A. Infrastructure Acceptance

Must pass:

```text
Fake Harness / controlled fixtures
```

for:

```text
PASS
FAIL
ERROR
TIMEOUT
CANCEL
LIMITED
Verifier ERROR
Environment ERROR
```

AgentBenchKit must correctly distinguish:

```text
execution failure
candidate correctness
analysis failure
cleanup failure
```

Additional requirements:

```text
fresh verifier is protected
candidate collection is complete
timeout/cancel leaves no residual execution
trajectory/artifacts remain readable after failure
```

---

## B. Real Agent Acceptance

### Required Agent 1

```text
Nexus v0.2.0
```

must run against `micro_swe`.

The acceptance condition is **not** a required high pass rate.

AgentBenchKit passes if it:

```text
launches Nexus correctly
provides correct workspace
records observable trajectory
freezes candidate
independently verifies candidate
correctly reports PASS/FAIL/ERROR
persists evidence
```

Nexus may fail tasks; that does not imply AgentBenchKit failed.

### Required Agent 2

At least one mature third-party Coding Agent, preferably:

```text
Codex
```

must run the same `micro_swe` contract.

No Agent source modification required.

This proves Harness abstraction is real.

---

## C. Evaluation Acceptance

Must demonstrate:

```text
Deterministic Verifier
candidate_pass
sample_success
Rubric
optional LLM Judge
Failure / RCA
```

Required invariants:

```text
Judge failure does not change deterministic correctness
candidate correctness does not erase timeout/cancel/limit facts
missing observability is N/A, not zero
```

---

## D. Regression Acceptance

At least one real comparison:

```text
Run A
vs
Run B
```

Possible controlled changes:

```text
Nexus config A vs B
Nexus version A vs B
same model with Nexus vs Codex
model A vs model B under same Harness
```

Compare must show:

```text
end-to-end success
candidate pass
coverage
latency
steps
tool calls
failure distribution
IMPROVED / REGRESSED / UNCHANGED / INCONCLUSIVE
```

and surface comparability warnings.

---

## E. Product Experience Acceptance

A normal user must be able to:

```text
agent-bench run ...
        ↓
see progress
        ↓
receive run-id
        ↓
agent-bench view <run-id>
        ↓
inspect browser UI
```

Viewer must make understandable:

```text
what task ran
which Agent ran it
where it ran
what candidate it produced
whether candidate passed
whether sample succeeded end-to-end
what trajectory was observed
why failure was attributed
what metrics were produced
```

---

## F. Public Benchmark External Validation

Not a hard V0 blocker unless time permits.

Preferred:

```text
SWE-bench Lite dev
```

using:

```text
1–5 pinned samples
```

Purpose:

```text
prove external benchmark adaptability
```

not:

```text
produce a leaderboard score
```

---

## G. V0 Success Definition

> AgentBenchKit V0 is successful when it can credibly and reproducibly evaluate at least two different Coding Agents under the same normalized Benchmark / Environment / Verifier contracts, correctly separate execution state from candidate correctness, preserve auditable evidence, explain failures with bounded claims, and compare two runs without silently mixing incomparable conditions.

A high Agent pass rate is **not** itself a V0 release requirement.

---

# 39. Git / Commit Policy

Development branch:

```text
feature/v0-implementation
```

Rules:

1. Work only on the feature branch during V0 implementation.
2. Each phase ends with tests and one coherent commit.
3. Push after every phase.
4. Do not force-push.
5. Do not rewrite pushed history.
6. Commit body includes:
   - what changed
   - why
   - verification performed
   - known limitations
7. If a frozen invariant must change, stop and report before implementation continues.
8. Final merge into `main` happens through PR.

---

# 40. Astra Freedom Boundary

Astra has maximum implementation freedom inside frozen contracts.

Astra may choose:

```text
class decomposition
internal helper structure
exact SQLite schema
async worker implementation
template layout
test organization
specific Docker invocation library
```

Astra must not silently change:

```text
external Agent integration principle
whole-Agent Environment semantics
fresh independent verification
candidate_pass/sample_success distinction
metric semantics
status separation
sample/retry semantics
trajectory capability semantics
artifact/versioning rules
deterministic correctness authority
lightweight local-first scope
```

If a frozen boundary is technically invalid, Astra must stop and explain:

```text
blocking contract
evidence
recommended change
impact
```

before coding around it.

---

# 41. Final Frozen Summary

```text
Project:
AgentBenchKit

Positioning:
Lightweight Coding Agent Evaluation & Benchmark Infrastructure

Agents:
Nexus v0.2.0
+
at least one second real Coding Agent (prefer Codex)

Benchmark:
micro_swe
Python-only
8–15 lightweight tasks

Optional public validation:
SWE-bench Lite dev
1–5 pinned samples

Environment:
HostProcess for trusted development
Docker for formal isolated evaluation

Correctness:
Fresh Independent Verification

Candidate Correctness:
candidate_pass

End-to-End Success:
sample_success

Trajectory:
append-only JSONL
versioned
capability-aware
nullable where unobservable
evidence-oriented

Statistics:
end_to_end_success_rate
candidate_pass_rate
coverage_rate
pass@k with conservative N/A rules

Evaluation:
Deterministic Verifier
+
Rubric
+
Optional LLM-as-a-Judge

Statuses:
Execution
Agent outcome
Verification
Analysis
Cleanup
all separate

Failure Analysis:
facts
termination
suspected ownership
confidence
evidence

Reproducibility:
Resolved Run Manifest

Persistence:
Filesystem evidence
+
SQLite query index
+
all Physical Executions preserved

Developer Workflow:
Replay
Regression Compare

UI:
CLI
+
local read-only Web Viewer

Implementation:
Vertical Slice First
phase commit + push

Excluded:
MQ / Redis / PostgreSQL / Celery / Kubernetes /
distributed workers / full SWE-bench /
mandatory Agent source modification /
online observability platform
```

---

# 42. Final Review Questions for Codex

Please perform one final architecture review.

Only report blockers or material contradictions that would make V0 results untrustworthy.

Specifically verify:

1. Is `candidate_pass` vs `sample_success` now unambiguous?
2. Are end-to-end success, candidate pass rate, coverage and pass@k computed from consistent sample sets?
3. Is the conservative pass@k N/A rule acceptable for V0?
4. Are Physical Executions preserved without overwriting startup retry evidence?
5. Does Phase 1 now include enough minimum runtime safety for a real Nexus execution?
6. Are nullable trajectory fields consistent with Harness capability declarations?
7. Is the V0 release gate strong enough to prove AgentBenchKit rather than merely prove Nexus?
8. Is requiring Nexus + a second Agent sufficient to validate Harness generality?
9. Is Micro-SWE appropriate as the primary internal validation benchmark, with public benchmark adaptation only as external smoke?
10. Is there any remaining architecture blocker before autonomous implementation begins?

Please do not propose additional scalability infrastructure unless it is required to preserve correctness or auditability.
