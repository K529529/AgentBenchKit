# FeatureBench Fast v1.1

- Dataset: LiberCoders/FeatureBench, revision
  `76b4a4566e04f4bcc13c35125d4f301791efa736`, split `fast`, all 100 lv1 tasks.
- Official evaluator: LiberCoders/FeatureBench commit
  `8d4e347ec57546685c5a87e8676bf575db022ea6` (package version differs from dataset version).
- Metadata source: official dataset and the owner's 2026-10-08 registry snapshot.
  Catalog contains prompts, repository/base revisions, immutable image references
  and content hashes. Original correctness/test inputs are not included in prompts.
- Correctness is the completed official instance report's `resolved` boolean.
  Missing reports, worker errors and incomplete evaluations are ERROR, not FAIL.
  ABK does not reimplement F2P/P2P grading, including official skip/xfail semantics.
- Windows supports discovery/configuration. Execution uses Linux/WSL and Docker;
  the official evaluator imports `fcntl` and does not import on native Windows.

## Discovery and configuration (no model calls)

```sh
agent-bench tasks featurebench
agent-bench make-config featurebench --all-tasks --output full-fast.json
agent-bench make-config featurebench \
  --evalset examples/evalsets/featurebench-fast-evalset-v1.json \
  --output fixed-16.json
```

The full configuration is a plan, not a requirement to run 100 tasks. The frozen
16-task file is validated by content fingerprint and its declared order is kept.
The 16 x 2 formal experiment remains out of implementation scope.

## Runtime preparation

Install the pinned official evaluator in a separate Linux environment, alongside
ABK. Keep its source checkout clean and pass its absolute path in configuration.
`agent-bench fetch-data featurebench --output fast.json` downloads the pinned
parquet, verifies its SHA256 and converts its 100 rows; `pyarrow` is required.
Dataset rows are verified against the bundled manifest before execution.

A task's inference image must derive from that task's pinned official image.
`python -m agentbenchkit.benchmarks.featurebench.build --help` describes the Nexus
image builder. The unchanged Nexus source archive is hash-pinned to V0 acceptance;
its isolated Python environment does not replace the official testbed interpreter.
The official evaluator always uses the original pinned image, not the inference
image. No image is pulled by discovery/config generation.

Generate a single-task configuration with `--task`, `--dataset`,
`--official-source`, `--evaluator-python`, and `--agent-image`, then:

```sh
agent-bench run featurebench nexus --env docker \
  --benchmark-config one-task.json --model-config nexus-model.json \
  --prepare-timeout 1800 --agent-timeout 900 --verify-timeout 1800 \
  --startup-retries 0 --concurrency 1
```

Use a Linux filesystem for execution workspaces so symlinks and executable modes
are preserved. Baseline preparation is delegated to official RuntimeHandler.
ABK retains physical preparation logs, the frozen patch and changed files,
trajectory, upstream logs/reports and separate cleanup status. Candidate patch
collection uses an independent Git index; the Agent's `.git` cannot alter it.

Nexus pipeline smoke is recorded in implementation-status.md (LIMITED / official FAIL).
Qoder CN pipeline smoke is also recorded (20-turn LIMITED, empty candidate, official FAIL);
see [Qoder setup](qoder.md) for its pinned image and managed account protocol.
A smoke is pipeline evidence,
not a full-Fast or fixed-evalset accuracy estimate.

For a selection spanning multiple images, set `agent_images` in the generated JSON
as a map from each pinned official image reference to its built inference image.
`agent_image` is the single-image fallback. Each selected task resolves and records
its actual immutable inference image ID; a base-image mismatch fails preparation.
Run image groups serially on this 32 GB host. The run-level environment identifies
the probe image; execution-level environment evidence identifies each task image.

The bundled catalog is derived from the official FeatureBench dataset
(https://huggingface.co/datasets/LiberCoders/FeatureBench) and official evaluator
(https://github.com/LiberCoders/FeatureBench). Their licenses and upstream task
repository licenses remain applicable; ABK does not claim authorship of task text.
