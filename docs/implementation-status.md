# Implementation and release status

Contract: [architecture-v0.3.1.md](architecture-v0.3.1.md).
A failed evaluated Agent is not automatically a toolkit failure.

## Current V0.2 implementation

All requested adapters and Harness integration are implemented; real smoke pipeline
acceptance is complete. Final summary: [V0.2 notes](release-notes-v0.2.0.md).
FeatureBench/Nexus FAIL, SWE-bench Lite/Nexus PASS, Polyglot Python/Nexus PASS,
Polyglot JavaScript/Nexus FAIL, FeatureBench/Qoder LIMITED with empty candidate FAIL.
Those negative outcomes are preserved. No full benchmark or formal 16 x 2 run.
The detailed chronological phases below retain historical blockers and failed
attempts; later entries explicitly resolve them. No release/merge is implied.

## Historical v0.1.0 baseline

- Final local suite: **175 passed / 7 opt-in Docker skipped**; locked sync, Ruff,
  strict Windows/Linux-target mypy (including examples), CLI help and benchmark validation PASS.
- sdist/wheel build and contents, package version 0.1.0 / MIT, local documentation
  links, example syntax/type checks and tracked/archive secret scans PASS. Fresh
  wheel installation also passes CLI, all eight task checks and external type checking.
- Windows/Ubuntu CI checks pass for the release-finalization state; workflow history
  remains available in [GitHub Actions](https://github.com/K529529/AgentBenchKit/actions/workflows/ci.yml).
- Existing real evidence: Nexus 8/8, Codex ChatGPT smoke 2/2, shared ModelSpec regressions,
  Docker fresh verification, browser Viewer review, replay/compare and full real Judge COMPLETED.
- Real Judge artifact `f0f559a29ce744fda95aed0f40842c17.json`: HTTP 200 / stop,
  four strict dimensions; original evidence and historical failed Judge artifacts unchanged.
- Repeated-tool observation is implemented; Stagnation is deliberately deferred.
- Real Codex explicit API inference is NOT RUN; public SWE-bench adapter is deferred.
- Release finalization changes documentation, an example and typing package metadata only;
  frozen evaluation semantics remain unchanged.

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
| 7: rubric/optional judge | PASS (controlled + real Judge) | Four dimensions; isolated HTTP worker deadline; versioned results; Judge failure/replay preserve correctness |
| 8: viewer | PASS | Read-only/XSS/path/size tests; actual browser run/sample pages checked; model/provider and subscription-smoke limits visible |
| 9: public benchmark | OPTIONAL, NOT RUN | |
| 10: release finalization | PASS | Current checks and acceptance below; no frozen evaluation semantics changed |


## Hardening history

- Repeated-tool observations added with 19 regression cases; existing real trajectories
  replayed without changing evidence/verdicts. See [trajectory analysis](trajectory-analyzers.md).
- Safe Judge diagnostics exposed truncation and then a schema mismatch. The old generic
  error record remains intact; it cannot retroactively supply its swallowed exception.
- Canonical Judge output now shares an exact prompt/schema, rejects ambiguous shapes,
  and receives framework-owned versions only after validation. Full live Judge validation
  passed; see [diagnostics](judge-diagnostics.md).

## README Viewer image repair

PASS: replaced the invalid WebP reference with the original PNG (byte-identical to
the supplied screenshot; all PNG chunk CRCs and local image links verified).
Centered preview, linked full-size image and caption added. Ruff, mypy and the
existing suite pass: 175 passed / 7 Docker skipped; no evaluation code changed.

## Viewer presentation refresh

PASS: refreshed the shared Viewer styling and run overview hierarchy; preserved
all status values, model-comparability warnings and expandable raw evidence.
Sample attribution is now expandable: UNKNOWN / confidence 0.0 remains visible
when opened, with the original uncertainty statement. No evaluation semantics or
stored evidence changed.

README now uses an unmodified browser capture of real Nexus / qwen3.8-flash /
Docker run `20261007T085706Z-6489516b` (one task, one successful sample), with a
680px preview and link to the original JPEG. This is a UI example, not a leaderboard.
Actual browser checks cover the overview, sample navigation and attribution
expansion; existing Viewer tests cover read-only evidence integrity and security.
Ruff and mypy PASS; full suite: **175 passed / 7 opt-in Docker skipped**.
No additional model calls or Docker acceptance runs were needed for this UI change.

## README two-column gallery

PASS: replaced the single 680px JPEG preview with two linked 360px PNG previews
(run overview and sample detail), each with a caption below. Both supplied PNGs
are byte-identical to their originals; chunk CRCs and README image/link targets
pass validation. No Viewer or evaluation code changed. Ruff and mypy PASS;
full suite: **175 passed / 7 opt-in Docker skipped**.

Gallery alignment follow-up PASS: both previews use a common 270px height with
natural aspect ratios and unchanged original-image links. Removed the preview
instruction and centered the remaining example caption. HTML attributes and
image targets checked; Ruff/mypy PASS; 175 passed / 7 Docker skipped.

## README visual identity

PASS: added original teal/navy SVG branding and an architecture overview, factual
Python/Harness/task/license badges, centered navigation and consistent section
headings. The two 270px gallery previews, original screenshots, all fenced CLI
examples, acceptance claims and evaluation boundaries are preserved. The textual
execution chain remains available in an expandable section.

Local browser preview verified the header, architecture diagram, navigation and
all eight images loading; both gallery images render at 270px height. This preview
approximates GitHub styling rather than asserting pixel-identical GitHub rendering.
SVG XML and local README link checks PASS. Ruff/mypy PASS; full suite:
**175 passed / 7 opt-in Docker skipped**. Only documentation/assets changed.

Final README copy polish PASS: applied the owner-selected tagline and shortened
the gallery caption only. Ruff/mypy PASS; 175 passed / 7 Docker skipped.

## V0.2 phase 1: Benchmark execution hooks

PASS (2026-10-08): Runtime delegates task manifests, preparation, candidate freeze
and independent verification through BenchmarkAdapter. MicroSweAdapter preserves
existing verifier semantics, Docker fresh verification and credential checks.
Benchmark identity is adapter-owned; correctness/sample_success rules are unchanged.
Scope and phase order are recorded in [V0.2 implementation](v0.2-implementation.md).

- Baseline: 175 passed / 7 opt-in Docker skipped; Ruff and mypy PASS.
- After hooks: 176 passed / 7 opt-in Docker skipped; Ruff and mypy PASS.
- Relevant real integration: all 7 opt-in Docker checks PASS (23.29 seconds).
- Real model smoke for new benchmarks: NOT RUN, pending adapter phases.
- Execution sandbox initialization is broken on this host; reviewed commands outside
  that sandbox were used. No Agent/model calls or large image pulls in this phase.


## V0.2 phase 2: FeatureBench Fast v1.1

PASS: full 100-task discovery, explicit selection/config generation and frozen
16-task/8-image evalset import. Dataset, evaluator and official image digests are
pinned. Official RuntimeHandler prepares the masked repository; official
run_instance owns F2P/P2P execution and grading. Runtime contains no repository or
FeatureBench conditions. Local fixture fields now belong to LocalTaskSpec.

Real Nexus pipeline smoke completed on 2026-10-08:

- Task: `pypa__packaging.013f3b03.test_metadata.e00b5801.lv1`, selected for its
  relatively small image from the frozen set before observing Agent results.
- Run: `20261007T231234Z-bfb89e93`; physical execution
  `5cecee636bfc4667bab35ef096a2546e`.
- FINISHED / Agent LIMITED (40 steps) / official FAIL / cleanup COMPLETED.
  Candidate frozen; sample_success=false. This is pipeline acceptance, not a
  solved task or a claim of benchmark accuracy. No performance-driven retry.
- Official report: patch applied, evaluation completed; F2P 275 success / 19
  failure; P2P 3508 success / 0 failure. ABK uses upstream resolved=false.
- Agent qwen3.8-flash, reasoning low, max output 16384; 40 reported model calls,
  input 1,330,177 tokens, cached input 982,784, output 25,269. No verified CNY bill.
- Candidate patch SHA256:
  `1f7555ab3025fae1a72f72375df569b50f135a12608b6cf0c92a5895180c1dbf`.
- Official worker result SHA256:
  `367801b34ee7d9210157acc8fd03a2c16669f4715a8661a21c8f7c722af617f0`.
- Exact pre-commit smoke source snapshot SHA256:
  `6e2738195d735cffd8a0c53f84a021419fe1877226cca4de1708881d8e5834b1`.
  Later type/config/resource-recovery hardening is regression checked separately;
  it is not misrepresented as the exact source used for model inference.

Evidence is local and ignored: `.agentbenchkit/v02-results/<run>` and
`.agentbenchkit/smoke-source-3.zip`. Earlier physical runs remain preserved:
`20261007T230422Z-756533b5` failed PREPARE on docker-py's 60-second snapshot timeout;
`20261007T230815Z-2f1ffcaf` failed before model calls on the container home UID.
The fixes use bounded Docker CLI snapshotting and the existing host UID mapping.
No agent source, official test logic or credential boundary was changed.

Official evaluator controls PASS: empty patch -> FAIL, reference patch -> PASS.
Final-code verification of the frozen Nexus patch is retained separately in
`.agentbenchkit/featurebench-final-verification` (no additional model calls).

Validation: 185 passed / 7 opt-in Docker skipped; Ruff/mypy PASS. Real Linux/WSL
Docker regression: 7 passed. Windows Docker retry: 4 FAIL / 3 PASS due to host
PermissionError reading container-created files in Python's 0700 pytest directory.
A same-machine no-model comparison reproduced it with BOTH committed V0 and V0.2;
ordinary directories worked in both. This host ACL limitation remains documented,
not hidden by a permission relaxation. Linux ext4 workspaces are required for the
public benchmark execution path. No managed container or ephemeral snapshot was
left after the real smoke.

SWE-bench, Polyglot and Qoder real acceptance are still NOT RUN at this phase.
No full benchmark or formal 16 x 2 experiment was run.


## V0.2 phase 3: SWE-bench Lite

PASS: full 300-task discovery/selection/config generation, pinned data fetch and
an adapter using official SWE-bench v4.1.0 (`726c5461e2ef52d83cf1ea2107870a8bb3328d57`).
The published evaluator matches the original Lite schema. The adapter delegates
spec creation, patch application, tests and grading to upstream. Only immutable
image references, evidence location and resource ownership labels are wrapped.
FeatureBench and SWE share bounded worker execution and unchanged Nexus image
construction; no benchmark-specific execution logic was added to Runtime.

Real acceptance PASS (2026-10-08):

- Task `psf__requests-1963`, selected as the first Requests task in the pinned
  catalog for a small repository smoke, before any Agent results.
- Official image digest:
  `swebench/sweb.eval.x86_64.psf_1776_requests-1963@sha256:5ca751c160affa98d160831608fffe3e2c4fb61c4fb2dad2b147ef2a885088e4`.
- Reference-patch official evaluator control PASS before model execution.
- Run `20261007T233529Z-37ae1426`; execution
  `c01afafe3562419d90d97d6aa77800f2`.
- FINISHED / Agent COMPLETED / official PASS / cleanup COMPLETED;
  candidate_pass=true and sample_success=true.
- Official F2P 7 success / 0 failure; P2P 112 success / 0 failure.
- Same Nexus/model controls as phase 2, 29 model calls; reported input 323,779,
  cached input 289,280 and output 7,706 tokens. No verified monetary charge.
- Patch SHA256 `3985b562350126e1c731c82171de4827fa9117bc30c0e1c6e7868c21769a295b`.
- Official result SHA256 `83bb3924026a03be57afd75da04c7e0aec9ec57790312870debde1a5457dc1fe`.
- Exact inference source snapshot `.agentbenchkit/swe-smoke-source.zip`, SHA256
  `9a21032a32df431832bc4c1eb37faed2f60deb09c78f97d0d20df6ec1b8b74ea`.
- Immutable evidence under `.agentbenchkit/v02-results/<run>`; reference control
  under `.agentbenchkit/swe-controls/gold`. Runtime artifacts remain ignored.

Regression: 186 passed / 7 opt-in Docker skipped, Ruff and mypy PASS. Real upstream
control and Nexus E2E PASS; no full 300-task run. Phase 2's official FeatureBench
verdict remains unchanged; no additional FeatureBench model calls were made.
Polyglot and Qoder real acceptance remain NOT RUN at this phase.


## V0.2 phase 4 checkpoint: Polyglot (acceptance pending)

PASS: all 225 tasks are discoverable/selectable/configurable across six languages;
package build includes complete 100/300/225 public catalogs. The adapter hides
upstream tests and reference examples from Agent workspaces, collects only the
upstream solution scope, and executes original pinned run_unit_tests /
cleanup_test_output function bodies in independent verification. This is the
owner-selected single Agent execution protocol, not official two-round scoring.

Source pins and commands are documented in aider-polyglot.md. Official Python
control: starter FAIL, reference PASS. JavaScript starter FAIL; official reference
FAIL with 14/16 passing and two TypeError failures because Jest 30 removed
expect(...).toThrowError. Upstream benchmark Dockerfile installs unpinned jest;
the frozen dataset package.json explicitly requires ^29.7.0. The proposed image
fix is Jest 29.7.0, preserving upstream tests/scripts/grading. Owner confirmation
of this upstream configuration conflict is pending. No Polyglot model calls have
been made and the >=2-task real Nexus acceptance is NOT RUN.

Image build evidence: .agentbenchkit/polyglot-build-npm1099.log. Node 20 retained;
npm 10.8.2 stalled, npm 10.9.9 completed the same dependency installation.
Initial image config ID: c9153a8cc58a5458c96373a34c85f259e825569dba184a755ca84c24a6bda831.
Controls are preserved under .agentbenchkit/polyglot-controls and Linux
/tmp/abk-polyglot-controls. The first JavaScript starter archive copy failed on
container-only dependency symlinks after verification; ext4 evidence remains
intact, and the subsequent reference control used symlink-preserving archival.
No failed control is an Agent result or accepted solved task.

Independent Viewer/documentation work: pages show Benchmark and generic adapter
protocol notices; sample pages show evaluation_protocol. Read-only routes and
Replay analysis passed against the real FeatureBench and SWE runs. SHA256 of all
55 existing evidence files stayed unchanged. Cross-benchmark Compare returned
formal_comparable=false with benchmark/tasks/environment differences. README and
benchmarks.md distinguish complete catalogs from actual execution/acceptance.

Regression: 190 passed / 7 opt-in Docker skipped; Ruff/mypy PASS. Linux real Docker
regression after generic verifier workspace/network controls: 7 passed (25.03s).
QoderHarness and its FeatureBench real smoke remain pending the owner's configured
CLI/login/BYOK; do not label V0.2 acceptance complete. No full benchmark was run.


## V0.2 phase 4 acceptance: Jest correction and two-language Nexus smoke

Completed on 2026-10-08. The owner approved Jest **29.7.0**, matching the pinned
JavaScript dataset package.json ^29.7.0. Upstream Dockerfile's unversioned Jest
had resolved to 30.5.2, removing toThrowError and breaking the reference control.
The derived image changes only that dependency; official test files, npm-test.sh,
run_unit_tests and grading logic are unchanged. Their fingerprints and clean
Linux checkout status were checked before execution. Older failed controls remain
preserved. Adapter rejects images without the declared Jest 29.7.0 pin.

Controls repeated on the corrected image: Python starter FAIL / reference PASS;
JavaScript starter FAIL / reference PASS. All four cleanups completed. Evidence:
.agentbenchkit/polyglot-controls-jest29; build log: .agentbenchkit/polyglot-build-jest29.log.
Image ID: sha256:7be4e8877180fde90295e2fa7c66a5f58b1c491b40fd4274b0adf0d007cfe3fe.

Real Nexus smoke run: `20261008T001621Z-17a32242`, exactly two tasks in serial,
one sample each, startup_retries=0, max_steps=30, agent timeout 600s. The two task
IDs were selected before model outcomes; no result-driven task replacement,
second repair round, candidate edits or model reruns were performed.

- Python affine-cipher: FINISHED / Agent COMPLETED / official PASS (16/16) /
  cleanup COMPLETED; candidate_pass=true, sample_success=true.
- JavaScript affine-cipher: FINISHED / Agent COMPLETED / official FAIL (14/16) /
  cleanup COMPLETED; candidate_pass=false, sample_success=false. Both failed
  assertions concern exception message text: official expected `a and m must be
  coprime.`, candidate produced `Key and alphabet length must be coprime (a and m
  must be relatively prime).` Jest 29 executes these assertions normally. This is
  a candidate failure, distinct from the earlier Jest 30 infrastructure conflict.
- Real two-language pipeline acceptance is complete; solved tasks are 1/2. This
  small single-run hidden-test smoke is not an official Aider two-round score.
- Nexus v0.2.0 is unchanged; qwen3.8-flash, reasoning low, max output 16384.
  Combined reported usage: 17 model calls, 122,108 input tokens (92,672 cached),
  12,072 output tokens. Monetary cost remains unverified/null.

Exact execution source snapshot .agentbenchkit/polyglot-smoke-source-jest29.zip:
`452bc20f9d5362c80499e92aaa932cf5dc585de3435c4dc186b89a999ad551b6`.
The checked-in runtime source was not edited during either model execution, and
all archived source bytes were compared with final source after completion.
Local immutable evidence: .agentbenchkit/v02-results/20261008T001621Z-17a32242.

Task `javascript--affine-cipher`:

- Physical execution: `756b88a712f742be9a035cc867c35631`.
- Patch SHA256: `451f1e4ffc326c05ba72f4341dc996575b2fc508cb657d0bde357127dbfd918d`.
- Official report SHA256: `714ef224bb1bf4a04eb0c35bddb2fc280462e89eb950e3e4c478d428cff927d1`.

Task `python--affine-cipher`:

- Physical execution: `00f9359293154beaa7bc9db3fb0310be`.
- Patch SHA256: `051f525bc865bcdba6b148776400f46fb1dd94966bd406b8d424dda3557456e0`.
- Official report SHA256: `c308300f93011036699ef27bf76370dee0f21465ff076efdf1ab2b78c03bceb5`.

Validation: 193 passed / 7 opt-in Docker skipped; Ruff and mypy PASS. The four
real controls and both Nexus executions ran in Docker. Viewer and Replay analysis
read the new run successfully; protocol notices render and SHA256 of all 40
existing run evidence files remained unchanged. No full 225-task run occurred.
QoderHarness / Qoder FeatureBench smoke remain pending CLI/login/BYOK configuration;
V0.2 as a whole is not yet fully accepted.


## V0.2 phase 5: Qoder CN public SDK integration

Qoder CN CLI 1.1.65, qodercn-agent-sdk 1.0.15, requested Qwen3.8-Flash / low /
16384 output tokens. The owner authorized their configured account. Public model
listing and the real SDK messages both confirmed Qwen3.8-Flash. Managed account
runs are subscription_smoke; no equivalent Bailian API endpoint is claimed.
Login cache files enter Docker tmpfs through stdin, never image layers or evidence.
SDK settings sources, MCP servers and skills are empty. No external Agent source
was changed. Official FeatureBench correctness remains upstream-owned.

Initial observed balance: 390 Credits (400 total, 10 used). The first launch failed
before inference because CLI --version creates a config directory on a read-only
root. Version probing now uses a disposable config directory. Original log:
.agentbenchkit/qoder-featurebench-version-failure.log. No model calls in that launch.

First physical inference: `20261008T012023Z-391a0ae2`, execution
`ce8d71de8c064f3198271215840ab07d`, task
`pypa__packaging.013f3b03.test_metadata.e00b5801.lv1`.
In-session get_usage_info returned empty while inference continued. Independent
no-query SDK checks repeatedly returned 390 Credits. At 5.665586718 observed
request Credits (all billable=false), the operator sent SIGINT to the owned Agent
container. This run is **ERROR / UNKNOWN / official FAIL / cleanup COMPLETED**,
not accepted as a successful Harness integration. Its frozen candidate was empty;
upstream completed with patch_exists=false. Evidence, failed attempt and external
stop record are preserved. No task replacement or candidate edit occurred.

The corrected driver uses a separate no-query SDK connection for 10-second account
polling, rejects empty snapshots, and independently deduplicates request Credits
by explicit request_id before applying the cumulative threshold. The owner raised
the next attempt's cumulative threshold to 10.0 Credits; per-request 2 Credits,
20 turns and 600 seconds remain. These are observed interruption thresholds with
possible in-flight overshoot, not provider-enforced billing caps. A request's
billable flag, reported Credits and observed account delta remain distinct.

Streaming message IDs are not counted as requests. Full model-call count is null;
observed request count remains in terminal evidence. All-zero managed token
placeholders normalize to null; raw SDK messages are preserved. Qoder tool input
objects support repeated-call observations, and is_error supports TOOL_ERROR RCA.
Neither analysis changes the official candidate verdict.

Final driver source archive .agentbenchkit/qoder-smoke-source-r2.zip SHA256:
`520a64c59c00e0a956747fc147b54a805fb7a482fb594d0b4286ccacc7dfd311`.
Driver wheel SHA256:
`01dd43802e4ab710b7012a9495956fc1fceb3dd8ad421a43b1c24394106b1205`.
Inference image abk-featurebench-packaging-qoder:v0.2.0-r2:
`sha256:f72b2ee702b561d1899f947c350d76cbc872efede54c5ae1e1205aa65fb7711d`.
The wheel retains pre-release package version 0.1.0; its exact source hash is the
implementation identity, not a claim that the final V0.2 package was already released.

Validation so far: 202 passed / 8 opt-in Docker skipped; Ruff and mypy PASS.
Real Linux Docker regression: 8 PASS, including opaque login-cache tmpfs injection,
file permissions, absence from Docker inspect and complete cleanup. Real final-image
SDK dual-connection preflight PASS without any prompt/model call. Full catalog CLI
checks found/configured 100/300/225 tasks, fixed selection stayed 16, and all eight
micro_swe no-op/reference controls produced FAIL/PASS. No full benchmark was run.


Corrected real Qoder run: `20261008T013419Z-9762cc1a`, execution
`d01141a9a47d4b1c8ee939730a92e4b2`, same fixed packaging task.
**FINISHED / LIMITED / official FAIL / cleanup COMPLETED**. SDK returned
error_max_turns at 20 turns; process exit 0, no timeout, no protocol error and no
output truncation. Candidate was frozen with no changes: the official evaluator
completed and rejected the empty patch (patch_exists=false), so no F2P/P2P tests
were run. This is valid negative pipeline evidence, not a solved FeatureBench task.
No retry was made to improve that verdict.

- 20 observed unique billing request IDs; reported request Credits 4.518009265,
  all billable=false. SDK ResultMessage total_credits=0. Account remained
  390 before, during (26 snapshots), after, and in an independent post-run query.
  Thus observed account decrease was 0 Credits; delayed billing cannot be excluded.
- 28 valid usage snapshots total; no empty snapshots or monitor errors in this run.
  The 10-Credit cumulative and 2-Credit single-request thresholds were not reached.
- Empty patch SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
- Official result SHA256: 358314f4620b7518937e65327882c166aa4d2746326e94136651d20c48dbfd78.
- Final source bytes matched the frozen execution archive. Known opaque credential
  bytes/base64 were absent from both physical-run archives; no .auth cache persisted.
- Viewer, Replay and Compare read the result successfully; all 19 original files
  remained byte-identical. Trajectory complete, 20 public tools analyzed, no repeated
  input observations. Full model calls and token counts remain unavailable, not zero.
- Prior real Feature/SWE/Polyglot and failed Qoder evidence also passed Viewer/Replay
  checks with 111 pre-existing files unchanged. Qoder/Nexus comparison correctly
  returned formal_comparable=false. Local evidence: .agentbenchkit/v02-results.

The required Qoder real E2E pipeline acceptance is complete. Correctness is FAIL;
this is not an official benchmark score. Final package/docs regression remains the
last V0.2 step; no further model execution is required for the requested scope.


## V0.2 final regression and scope closure

Package and CLI version are 0.2.0. README, benchmark/Harness/model guides, Viewer
protocol/account notices and [V0.2 summary](release-notes-v0.2.0.md) are current.
No architecture additions beyond the requested Adapters/Harness were introduced.

- PASS: uv sync --locked; uv run pytest **202 passed / 8 opt-in Docker skipped**;
  uv run ruff check .; uv run mypy; uv run mypy --platform linux.
- PASS: independent real Linux Docker regression **8/8**, including the new
  private opaque-cache path. Real public-benchmark executions/controls are listed
  in their phase records, separately from controlled test cases.
- PASS: all eight micro_swe no-op/reference FAIL/PASS controls, both source install
  and fresh 0.2.0 wheel install. Full public catalog discovery/config generation
  100/300/225, frozen evalset 16, and Nexus/Codex/Qoder CLI listing.
- PASS: sdist and wheel build; package metadata/version/py.typed; all three catalogs
  and Qoder modules in the wheel; no local runtime/IDE files in distributions;
  clean wheel installation and public catalog use from site-packages.
- PASS: local Markdown links, git diff --check, existing evidence immutability,
  Replay/Compare/Viewer against all real smoke types; managed-account comparison
  remains non-formal. Runtime/Core contain no public-benchmark/repository special cases.
- PASS: pushed phase 5 commit 67b4f47 has successful Windows/Ubuntu CI:
  https://github.com/K529529/AgentBenchKit/actions/runs/37714314826.
  Final commit CI is available in the same branch's Actions history.
- NOT RUN by scope: full benchmark model suites, fixed FeatureBench 16 x 2 formal
  evaluation, all other task/image/language/Harness combinations, a new paid Judge
  run, package publication, main merge or release tag.

All requested V0.2 implementation phases are complete. Stop adding features.
The remaining formal evaluation experiment is a separate owner-directed run.
Known single-run task failures and the earlier Qoder integration failure remain
visible; none is reclassified as a solved task or hidden by this scope closure.


## V0.2 hardening

Owner-authorized follow-up to baseline a380e903b7da17ea3f52aeee344fbcd2d7da9e2d,
on feature/V0.2.0-implementation. No Agent/model/Judge inference was invoked.

| Original finding | Final disposition |
| --- | --- |
| P0 Polyglot contamination | FIXED: explicit 225-task allowlist; hidden undeclared tests/references/approaches; protected Rust merge and audit hashes |
| P1 Qoder final usage fail-open | FIXED: None/empty after snapshot limits outcome, never COMPLETED; no-query observer retained |
| P1 Credits ambiguity | FIXED: request/session/account/billable observations separated, missing=null; legacy alias retained |
| P1 README stale claims | FIXED: V0.2 catalogs/adapters, candidate bounds and real smoke coverage reconciled |
| P2 Compare tasks waiver | FIXED: tasks membership alias cannot waive shared prompt/verifier/baseline/timeouts/metadata; explicit field selectors |
| P2 Environment hint | CLARIFIED + TESTED: prepared environment is Agent-only; outer hint remains for independent Adapter verifier construction |

The pinned inventory contains 225 tasks / 2,356 files, all matching catalog hashes.
One necessary non-solution helper (rust--doubly-linked-list) and one editable
solution (rust--react) contain two compile-fail doctests each. 24 tasks contain 37
additional verifier-only assets and 11 tasks contain approaches/articles. Generic
build/test declarations remain visible, as do go--counter's supplied test subjects.
See [Polyglot's policy and invariant](aider-polyglot.md#v02-hardening-agent-view-and-canonical-verifier).
Neither upstream checkout, official tests, commands nor grading logic changed.

Validation (free; controlled reference/starter code is not model acceptance):

- PASS: uv sync --locked; Ruff; strict mypy on Windows and with --platform linux.
- PASS: full local pytest **230 passed / 16 opt-in skipped**. Eight skips are
  existing Docker regressions, eight are new Polyglot Docker controls, executed
  separately below. The known non-fatal Starlette/httpx deprecation warning remains.
- PASS: existing Linux Docker regression **8/8** (27.47s).
- PASS: new Linux official Polyglot controls **8/8** (112.66s): Rust react,
  Rust doubly-linked-list, Python affine-cipher and JavaScript affine-cipher;
  every starter officially FAIL and every reference officially PASS.
- PASS: both Rust Agent views build with actual non-root Docker UID. react
  canonical doctests: **2 passed**; deliberately collapsed ID types: **2 failed**.
  doubly-linked-list pristine helper hash matches and separate advanced tests,
  including both compile-fail doctests, execute successfully. Its official default
  cargo test command is unchanged; advanced checks are extra regression evidence.
- PASS: all 225 real pinned task materializations/solution scopes and pristine
  verifier bytes; special support files; embedded test masking/restoration;
  abnormal/deleted/conditional anchors fail closed. Both CI platforms fetch the
  exact official dataset revision for these contracts; no fake file tree is used.
- PASS: Qoder None/empty final snapshot, missing-versus-zero request/account
  Credits, deduplication/billable flags, Replay/Viewer and Compare field controls.
- PASS: complete 100/300/225 CLI configuration generation, frozen FeatureBench
  16-task file fingerprint unchanged from baseline.
- PASS: seven historical public run manifests (including failed/partial runs)
  remain readable through analysis/Compare/Viewer; **171 existing files byte-identical**.
  No analyses are appended to historical runs. Accepted Qoder remains request
  Credits 4.518009265, SDK session 0, observed account delta 0, 20 billable=false
  observations; outcome/correctness unchanged. Both earlier affine smoke Agent
  input file sets are unchanged by the new visibility policy.
- PASS: sdist/wheel build and independent wheel install; new visibility policy,
  Rust parser and Credits modules included; no runtime artifacts packaged.
- NOT RUN by scope: any real Nexus/Qoder/Codex inference, paid Judge, full benchmark,
  frozen 16 x 2 formal evaluation, merge/tag/release/publication.

The first free Rust controls exposed an image permission bug, not a model or
correctness failure: non-root UID with default GID 0 could not traverse /root
(mode 705) to execute cargo. Four Rust controls ERROR; four affine controls passed.
The image builder now grants a+rx on /root. A new derived image, leaving the old
image/evidence intact, passed all eight controls:
`sha256:f49703ae1dd073037db5997a20b320609aeac2a184d1a346f916f0ed086ca6a6`.
Success and failure artifacts are retained under .agentbenchkit/v02-hardening-controls;
read-only compatibility/inventory records under .agentbenchkit/v02-hardening-inventory.

Remaining design limits: protected Rust merge intentionally rejects unsupported
anchor/attribute structures; upstream go--counter's deprecated test-authoring
contract is not repaired or regraded; C++'s official test build target needs hidden
tests; account delta may include other account activity/delayed billing; Compare
metadata is one explicit field rather than a per-key experimental-design API.
No Runtime benchmark/repository special case was introduced.

The coherent hardening commit
[`fff69a1ca498d083e61431376df7f48416faf2db`](https://github.com/K529529/AgentBenchKit/commit/fff69a1ca498d083e61431376df7f48416faf2db)
was pushed to feature/V0.2.0-implementation. Its
[Windows/Ubuntu CI run](https://github.com/K529529/AgentBenchKit/actions/runs/37751448148)
completed successfully: both platforms reported **230 passed / 16 opt-in skipped**.
No historical evidence or official correctness semantics changed.

## V0.2 final cleanup

This final cleanup retains the hardening acceptance above and adds only the
requested visibility regressions, public-facing documentation and the explicitly
authorized read-only Viewer presentation refresh.

- The supplied hardening HEAD already required the exact bare `pub` token for
  protected `ComputeCellId`. The check is unchanged; five new regression cases
  reject `pub(crate)`, `pub(super)`, `pub(in crate)`, `crate` and private visibility.
  No other Rust masking, restoration, candidate or official test semantics changed.
- Viewer: one run page contains the complete task map and result table, with local
  search and PASS/FAIL/N/A filters. Two runs share metric bars and a per-task
  comparison table. Original correctness/E2E dimensions, missing values and
  comparability warnings are preserved. The route additionally reads existing
  manifests for display names; Runtime, metrics and Compare semantics are unchanged.
- README is user-facing, documents the four built-in benchmarks and Agent extension
  path, and credits Archer as maintainer and OpenAI Codex as AI collaboration.
  The GitHub About description now names the built-in benchmarks.
- PASS: `uv run ruff check .`, `uv run mypy`, `uv run mypy --platform linux`.
- PASS: `uv run pytest` — **237 passed / 16 opt-in skipped**, with the same non-fatal
  Starlette/httpx deprecation warning. This extends the 230-test hardening baseline
  by five visibility cases and two multi-task/read-only Viewer regressions.
- PASS: local headless Edge rendered the 16-task synthetic dashboard and comparison
  at 1440px and 390px widths; filters, search, empty state, matrix anchor reset and
  no page overflow/JavaScript errors checked. The desktop browser tool failed to
  initialize, so the installed headless browser was used for development validation.
  README screenshots are explicitly labeled synthetic layout demonstrations.
- PASS: **171 historical evidence files byte-identical**, with no additions or
  deletions. The frozen 16-task FeatureBench selection is untouched.
- NOT RUN in cleanup: Docker controls (their prior **8/8 + 8/8** results remain
  above), Nexus/Qoder/Codex inference, paid Judge, full benchmarks or 16 x 2.
  No new model calls or model charges were incurred by this cleanup.

The cleanup is a single follow-up commit on `feature/V0.2.0-implementation`.
Its Windows/Ubuntu checks are recorded with that commit in
[branch CI](https://github.com/K529529/AgentBenchKit/actions/workflows/ci.yml?query=branch%3Afeature%2FV0.2.0-implementation).
The preceding hardening commit and its completed CI are linked above.
