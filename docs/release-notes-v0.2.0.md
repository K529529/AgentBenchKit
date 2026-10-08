# AgentBenchKit V0.2 implementation

AgentBenchKit now supports multiple Benchmark Adapters and external Agent Harnesses.
This implementation is delivered on `feature/V0.2.0-implementation`; publishing,
merging main and the later formal evaluation experiment are separate actions.

## Delivered scope

| Component | Implementation |
| --- | --- |
| FeatureBench Fast v1.1 | Full 100-task discovery/selection/configuration; pinned official evaluator |
| SWE-bench Lite | Full 300-task discovery/selection/configuration; official SWE-bench evaluator |
| Aider Polyglot | Full 225-task discovery/selection/configuration; hidden tests and official test semantics |
| Harnesses | Existing Nexus/Codex retained; Qoder CN public SDK added |
| Infrastructure | Lifecycle, isolated environments, immutable evidence, trajectory, metrics/RCA, optional Judge, Replay, Compare and Viewer retained |

Generic execution hooks delegate preparation, candidate freezing and independent
verification to each Adapter. Runtime has no repository/benchmark special cases.
No benchmark correctness logic is redefined in ABK. Polyglot uses one autonomous
Agent execution followed by official tests, not Aider's two-round test-feedback
protocol; its scores are not directly comparable with that official protocol.
Jest 29.7.0 resolves the upstream unpinned Dockerfile conflict without changing
official tests, scripts or grading. Reference controls passed before Agent smoke.

## Real smoke acceptance

All rows used real external Agents, frozen candidates and independent official
verdicts; cleanup completed. Pipeline acceptance does not mean that a task was solved.

| Benchmark / Agent | Task | Agent outcome | Official verdict |
| --- | --- | --- | --- |
| FeatureBench / Nexus | packaging test_metadata e00b5801 lv1 | LIMITED (40 steps) | FAIL; F2P 275/294, P2P 3508/3508 |
| SWE-bench Lite / Nexus | psf__requests-1963 | COMPLETED | PASS; F2P 7/7, P2P 112/112 |
| Polyglot / Nexus | python--affine-cipher | COMPLETED | PASS; 16/16 |
| Polyglot / Nexus | javascript--affine-cipher | COMPLETED | FAIL; 14/16, exception-message mismatch |
| FeatureBench / Qoder CN | same fixed packaging task | LIMITED (20 turns) | FAIL; empty candidate, official tests not run |

The final Qoder run was FINISHED with exit 0 and a public SDK max-turns result,
no timeout/protocol error/output truncation. It demonstrates the complete negative
pipeline, not a solved FeatureBench case. An earlier Qoder integration failure is
preserved separately and excluded from accepted integration evidence.

Exact run IDs, official report/patch hashes, source snapshots and failed controls
are recorded in [implementation status](implementation-status.md). No task was
replaced based on results, and no candidate was edited by ABK to improve a verdict.

## Qoder model and account observations

Public CLI 1.1.65 / SDK 1.0.15 confirmed Qwen3.8-Flash. Requested reasoning low,
max output 16,384. The corrected smoke used the owner's 10-Credit cumulative
observation threshold, 2-Credit per-request threshold, 20 turns and 600 seconds.

The accepted run reported 20 unique request IDs and 4.518009265 request Credits,
all billable=false; SDK session total_credits=0. Account balance remained 390
Credits before, throughout, after and in an independent post-run query. No observed
balance decrease occurred; this is not a promise about delayed/future billing.
Credits are not CNY and cannot be converted to a model cost estimate here.

A separate no-query SDK connection monitors account balance. Request Credits are
deduplicated by explicit ID. Empty/unavailable monitoring interrupts; in-flight
requests can overshoot thresholds. Full call count and all-zero token placeholders
remain null, while raw SDK evidence is preserved. Login caches are tmpfs-only.
See [Qoder guide](qoder.md) and [model contract](model-contract.md).

## Scope limits

- The frozen FeatureBench evalset v1 remains 16 tasks / 8 images, unchanged.
- No full 100/300/225-task model run, no formal 16 x 2 experiment, and no benchmark
  ranking or official aggregate score is claimed.
- Only documented smoke tasks/images/languages are execution-validated. Full
  discovery is distinct from validating every environment or Agent combination.
- Qoder managed-account and Codex ChatGPT login runs are subscription_smoke;
  Compare must not label them as formal API-comparable evaluations.
- No new paid Judge acceptance was needed: existing real Judge evidence and the
  full regression suite cover retained functionality; Judge never changes correctness.

Start with [benchmark configuration](benchmarks.md), then the individual
[FeatureBench](featurebench.md), [SWE-bench](swe-bench-lite.md),
[Polyglot](aider-polyglot.md) or [Qoder](qoder.md) guide.


## Implementation baseline validation

202 unit/integration tests passed; 8 opt-in Docker tests passed separately on Linux.
Ruff, strict mypy for Windows and Linux, locked dependency sync, source/wheel builds,
fresh wheel installation, all catalogs/config generation and eight micro_swe
no-op/reference controls passed. Viewer/Replay/Compare preserve original evidence
hashes and account-comparison restrictions. Phase 5 Windows/Ubuntu CI passed;
see [Actions](https://github.com/K529529/AgentBenchKit/actions/workflows/ci.yml)
for the final implementation commit's status. No additional model runs are needed
for this delivery scope.


## Hardening validation

The 202-test implementation baseline above is retained as historical evidence.
The subsequent hardening commit
[`fff69a1ca498d083e61431376df7f48416faf2db`](https://github.com/K529529/AgentBenchKit/commit/fff69a1ca498d083e61431376df7f48416faf2db)
was pushed and passed [Windows and Ubuntu CI](https://github.com/K529529/AgentBenchKit/actions/runs/37751448148).

- **230 passed / 16 opt-in skipped**, locally and on both CI platforms.
- Existing Linux Docker controls: **8/8** passed separately.
- Official Polyglot starter/reference controls: **8/8** passed separately.
- All 225 task visibility/scope contracts, protected Rust doctest restoration,
  Qoder final usage failure handling, Credits metrics and granular Compare checks passed.
- No new Nexus, Qoder, Codex or paid Judge model calls were made.
- All **171 historical evidence files** remained byte-identical. Official tests,
  evaluator commands and correctness semantics were preserved.

Details, including retained failed controls and remaining boundaries, are in
[the hardening acceptance record](implementation-status.md#v02-hardening).

## Final cleanup and Viewer

- **237 passed / 16 opt-in skipped** locally after five protected Rust visibility
  regressions and two dashboard regressions; Ruff and strict Windows/Linux mypy pass.
  The existing bare-`pub` check was already correct and remains unchanged.
- The read-only Viewer now provides a complete task map, searchable/filterable
  results and a side-by-side dashboard for two runs. It keeps candidate correctness,
  E2E success, missing data and comparison eligibility distinct. All 16 tasks fit
  within one run report; individual evidence pages remain available for drill-down.
- Desktop and narrow-screen rendering/interaction checks passed on synthetic data.
  README previews use clearly labeled synthetic records, not new benchmark results.
- The **202-test implementation** and **230-test hardening** results above remain
  separate historical milestones. The prior Docker controls (**8/8 + 8/8**) were
  not rerun during cleanup. No new model calls were made; all **171 historical
  evidence files** and official correctness semantics remain unchanged.

The final cleanup's commit-linked Windows/Ubuntu status is available in
[branch CI](https://github.com/K529529/AgentBenchKit/actions/workflows/ci.yml?query=branch%3Afeature%2FV0.2.0-implementation).

## Final release candidate validation

The current V0.2 release candidate has completed final verification.
The historical 202 / 230 / 237 test milestones above remain unchanged.

- **241 passed / 16 opt-in skipped**.
- **Windows CI: PASS**.
- **Ubuntu CI: PASS**.
- Ruff and strict mypy for Windows and Linux: **PASS**.

The reviewed candidate is
[`958ad4dcfc777b583fa30ca4a30b2d5d2e872a28`](https://github.com/K529529/AgentBenchKit/commit/958ad4dcfc777b583fa30ca4a30b2d5d2e872a28),
with [both CI platforms passing](https://github.com/K529529/AgentBenchKit/actions/runs/37759958562).
This release closeout only appends this validation record. Runtime, evaluation,
Viewer, Benchmark, Harness and official correctness semantics are unchanged.
No new model inference, paid Judge, full benchmark or 16 x 2 experiment was run;
historical evidence remains unchanged.
