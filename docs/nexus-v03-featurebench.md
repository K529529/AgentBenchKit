# Nexus V0.3 fixed16 adaptation and frozen execution

Scope: external Nexus CLI, FeatureBench Fast v1.1, Linux/WSL + Docker.
Nexus source is fixed to `0fd7fa4ba1f0bc8e313fca04cf1771c2a33720dd`.
No Nexus source, reference answer, official test, verifier or candidate-freeze changes.
The printed package version remains 0.2.0 and is not source identity.

## Adaptation

- `NexusHarness.import_model` retains explicit native sections in `HarnessOptions.nexus_config`.
  Model overrides remain represented in ModelSpec; native provider, compaction, security,
  runtime, multi_agent and capability controls are retained and compared in the manifest.
  Unsupported sections fail; other harnesses reject Nexus-specific configuration.
- Referenced compaction/model credentials are required, passed only to each isolated HOME,
  and included in redaction. No personal HOME, memories, sessions or config trees are copied.
- Builders accept full source commit plus SHA256 and validate Git ZIP comment and bytes.
  Inference images record base digest, source commit and archive hash as labels. The manifest
  records actual image IDs. Installed Nexus Python files were compared to the source archive.
- Root results exclude child terminal events. Full-tree statistics use actual model attempts,
  including compaction requests, never cumulative agent/result/compaction snapshots.
  Cached input is a subset, not added again; incomplete coverage stays unknown with known subtotal.
- The runner archives only redacted Nexus session JSONL, including children, before deleting
  the task workspace. It stores an archive manifest and explicit Agent duration separately
  from total prepare/agent/collect/verify/cleanup duration.
- `scripts/launch_nexus_featurebench.py` launches an independent tmux session. Credentials enter
  over stdin, are staged in a mode-0600 temporary file and unlinked by the runner. The frozen
  plan contains references only. The runner validates commits, file hashes and image IDs,
  executes samples=1/k=1/concurrency=1/startup_retries=0, and writes final exit status.
  A STOP file requests cancellation through normal cleanup. Individual FAIL/LIMITED/timeouts
  remain results; common startup/protocol/authentication/cleanup/disk failures stop the batch.

## Historical conditions and disclosed differences

The 16 Nexus cells in the completed `featurebench-16x2-restart-20261009` execution ledger
match the historical benchmark configuration and repository fixed16 evalset, in order.
Dataset revision: `76b4a4566e04f4bcc13c35125d4f301791efa736`.
Official evaluator: `8d4e347ec57546685c5a87e8676bf575db022ea6`.
All eight official image digests are retained. Each inference image derives from its own base;
verification continues in the original official image.

Retained: qwen3.8-flash, maas.qianwenaiapi.com compatible endpoint, low reasoning,
1,000,000 context, 16,384 max output, 300-second model request timeout, 50 Agent steps.
Phase seconds: prepare 600, Agent 900, collect 180, verify 1800, analysis 60, cleanup 120;
no overall timeout or startup retries. Agent container: 8192 MiB, 4 CPUs, 512 PIDs.

Changed: Nexus V0.2 commit `677fc997dcdc2f369fa8d4a667d400de99e35f84` to reviewed V0.3;
ABK adapter and Python dependency installation; explicit same-model compaction configuration;
explicit memory/MCP/Skills/web/telemetry off and local security. No private inherited memory.
Tonight multi_agent=false; tomorrow only multi_agent.enabled changes to true, with max_agents=3,
no nested agents, scout low, worker/reviewer high, and inherited role models.

The old experiment changed transport/cost guards, reference isolation and egress policy during
execution and retained historical interrupted attempts. This run uses a fixed policy from its
start and does not claim strict equivalence with all V0.2 cells. It reuses the historical
model-host-only CONNECT proxy/internal Docker network. Packaging/sympy historical reference
permission restrictions remain. V0.3 itself depends on packaging.version through LiteLLM;
its new private dependency copy therefore keeps runtime modules accessible but denies
packaging/metadata.py and packaging/__pycache__, the reference implementation relevant to
this panel's metadata task. The original official verifier environment is unchanged.

## Validation

PASS: Windows and Linux suites, each 225 passed / 37 opt-in skipped before final launcher
cleanup; new regression covers native config/credentials, child/root result separation,
request and snapshot accounting, missing usage, cached subset, archive scope/redaction,
archive-before-cleanup and source commit mismatch rejection. Ruff and strict mypy pass.

PASS: real independent single CLI smoke (one root, two model calls); real explicit delegation
CLI smoke (root plus one scout, five model calls); actual tools absent/present as configured;
local execution observed; installed-source hash equality; real compaction (reported usage,
checkpoint created). Smoke results are not benchmark samples. Initial synthetic compaction
probe lacked unique history sequence IDs; after fixing that probe fixture, the real compact
operation passed. An initial whole-package reference denial broke LiteLLM's packaging import;
this preflight failure was retained and narrowed as described above.

Formal execution status, final validation and image/config identities are recorded separately
in the immutable local experiment plan and evidence directory. Preparing scripts or images
is not proof that a benchmark has started. No second group is started automatically.


Preflight environment repair: original inference-image Aliyun apt endpoints returned HTTP 403.
Only inference-image apt sources were redirected to the reachable Ubuntu official archive;
task baselines and official verifier image digests were not modified. Initial failed official
prepare evidence is retained. The narrowed packaging isolation passed a further real CLI smoke.
Final affected tests: 31 passed; initial full suites: 225 passed / 37 skipped each platform.

PASS: final eight image IDs verified against all installed Nexus source-file hashes; metadata
reference unreadable as Agent UID while packaging.version remains usable. Official independent
prepare/collect/verify preflight completed and returned FAIL for an empty candidate, with clean
resource cleanup. This is a pipeline validation, not a scored model sample.
