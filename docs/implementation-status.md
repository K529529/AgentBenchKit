# Implementation and release status

Contract: [architecture-v0.3.1.md](architecture-v0.3.1.md).
A failed evaluated Agent is not automatically a toolkit failure.

## Current v0.1.0

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
