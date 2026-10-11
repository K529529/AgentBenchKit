# sh-agent experimental adapter (ABK V0.2)

Branch: `codex/sh-agent-c08-c17-c13`, based on `v0.2.0` (`a5ce6ec`).
This adapter is available through Python composition with `ShAgentHarness` and
`evaluate()`. It is not registered as an `agent-bench run` CLI agent.

## Agent and model identity

Upstream: https://github.com/csx-3323730970/sh-agent
Pinned commit: `26130e96732c51d83a7ece1d06325216831ee028` (version 0.1.0).
The upstream default in `config/settings.yml` is `deepseek-v4-flash`, not V4.1.
The model factory reads that file; the model is configurable, not hardcoded.

On 2026-10-11 the existing `maas.qianwenaiapi.com` provider catalog did not
include that exact default ID. One connectivity request with `max_tokens=8`
returned HTTP 404 `model_not_found` (no benchmark prompt was sent).
The owner then explicitly selected `deepseek-v4.1-flash`. Only
`model.chat_model` is changed in the derivative image's documented settings file;
the upstream Python files are hash-verified unchanged. Temperature remains 0.1.
Credentials arrive via environment variables and are not committed.

## Execution boundary and limitations

Upstream exposes an interactive CLI, without a noninteractive JSONL mode or a
separately versioned SDK. The standalone ABK worker calls the public
`code_agent.graph.compile_graph` callable used by that CLI and reproduces its
single-turn initial state. This is a source-pinned Python API integration, not
an advertised stable upstream SDK. Standard LangChain callbacks provide events.
The driver does not replace models, tools, prompts, nodes, or history reducers.
Redis checkpoint is disabled for independent fresh sessions, matching the CLI's
stateless fallback. PostgreSQL is disabled by upstream defaults.

A separate Python environment holds the evaluated agent and its dependencies.
The task testbed interpreter remains unchanged. Inference images derive from
already accepted task images; the pinned official evaluator uses the original
official images. Each image records the installed dependency versions and
unchanged task Git tree. The inherited testbed and network restrictions apply.

Unsupported explicit context/output token limits, reasoning effort, top-p,
seed, request timeout, model-call budgets, and Credits limits are rejected.
There is a 900-second Agent wall-clock limit. Native dependency retries and
LangGraph recursion limits remain unchanged; they are not ABK startup retries.
Streaming token usage is not promised by upstream and must remain N/A when
absent. Callback run IDs identify observable calls; they are not provider request
IDs. A normal finalizer return means Agent completion, not candidate correctness.

## Frozen three-task experiment

Order is C08, C17, C13; one physical execution per task; no automatic retries,
manual repair, prompt augmentation, or task replacement.

| Cell | Official task ID |
| --- | --- |
| C08 | `mlflow__mlflow.93dab383.test_trace_correlation.53c200a6.lv1` |
| C17 | `pydata__xarray.97f3a746.test_coordinate_transform.6cacb660.lv1` |
| C13 | `mwaskom__seaborn.7001ebe7.test_plot.b645d353.lv1` |

Dataset revision: `76b4a4566e04f4bcc13c35125d4f301791efa736`.
Official evaluator: `8d4e347ec57546685c5a87e8676bf575db022ea6`.
Budgets in seconds: prepare 600, agent 900, collect 180, verify 1800,
cleanup 120, analysis 60. Concurrency 1; startup retries 0.
Workspaces live on WSL ext4; evidence is archived to the experiment directory.
Only the configured model endpoint is reachable from inference containers;
public source/package hosts and direct external TCP egress are blocked.

Local evidence directory (ignored by Git):
`.agentbenchkit/experiments/sh-agent-c08-c17-c13-20261011/`.
It contains source identity, initial and final image receipts, dependency versions,
model/benchmark configuration, frozen manifest plus SHA256, network preflight,
execution ledger, phase timings, per-task raw evidence and analysis.
`final-image-receipts.json` is authoritative for the final driver image hashes;
the initial build used an earlier driver and is retained as preparation history.
A non-root testbed Git integrity probe failed on ownership; the read-only probe
was rerun as the repository owner. Neither preflight invoked a benchmark model.

These are three selected, previously known tasks, not a random sample or a
full FeatureBench score. Differences from prior Nexus runs include the evaluated
agent, model and native generation settings; no isolated causal attribution is
claimed.

The initial run `20261011T091039Z-02ff7205` was interrupted during PREPARE
before model inference. The official runtime initialization completed, but the
runner did not reach its Agent phase. Host available commit memory fell from
5.83 GB at launch to 0.518 GB; WSL then restarted. The exited preparation
container reported exit 137 with `OOMKilled=false`, so the precise cause is
unconfirmed. The original evidence was archived and hashed before ABK recovery
marked the run INTERRUPTED and removed only its owned container. Candidate and
verifier outcomes remain unavailable. C17/C13 are NOT RUN pending recovery.
Any owner-authorized continuation must use a separate manifest/ledger and retain
this first physical attempt; it must not overwrite the frozen original runner.

Owner-authorized recovery (2026-10-11): retain the interrupted C08 attempt and
allow one separate preparation retry, followed by C17/C13. The continuation lives
in `.agentbenchkit/experiments/sh-agent-c08-c17-c13-20261011-resume1/`, with a new
manifest and raw run root. Agent/model/task settings remain unchanged. A host
launcher waits for at least 12 GiB available commit and 6 GiB physical memory;
it sends SIGINT only to its verified experiment runner if available commit
falls below 2 GiB or physical memory below 0.75 GiB (2-second observation interval).
These operational thresholds are precautions, not guaranteed memory bounds.
No user applications are terminated and no global WSL settings are changed.
