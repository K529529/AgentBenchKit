# SWE-bench Lite

All 300 test tasks from `princeton-nlp/SWE-bench_Lite` are discoverable without
Docker, network access or model calls. Dataset revision:
`6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`.

The evaluator is official SWE-bench v4.1.0, commit
`726c5461e2ef52d83cf1ea2107870a8bb3328d57`. This published version consumes the
Lite dataset's original schema. The later development main expects additional
precomputed fields; ABK does not invent those fields or rewrite grading.

```sh
agent-bench tasks swe-bench-lite
agent-bench make-config swe-bench-lite --all-tasks --output lite-plan.json
agent-bench fetch-data swe-bench-lite --output lite.json
```

`fetch-data` requires pyarrow and verifies the pinned parquet SHA256 before
conversion. Execution validates all 300 row hashes; config generation never runs
the tasks. Only explicitly selected tasks are executed.

## Linux/WSL execution

Install the pinned evaluator in its own environment and pass both its clean
checkout path and Python interpreter. Use an ext4 workspace/output directory.
Official instance images are `swebench/sweb.eval.x86_64.<instance-id>:latest`, with
`__` encoded as `_1776_`; pull only selected images, then freeze their RepoDigest.

Build an inference derivative with the same unchanged Nexus archive used for
FeatureBench. `python -m agentbenchkit.benchmarks.images --help` lists the inputs.
It requires an immutable official base digest and installs Nexus in a separate
Python environment, preserving the testbed interpreter. The inference image label
records the official base. Configuration can additionally enforce it through
`image_pins` (official tag -> digest). `agent_images` maps task image tags to their
inference images for selections using several images.

```sh
agent-bench make-config swe-bench-lite --task psf__requests-1963 \
  --dataset /absolute/lite.json --official-source /absolute/SWE-bench-v4.1.0 \
  --evaluator-python /absolute/swe-venv/bin/python \
  --agent-image abk-swe-requests-nexus:v0.2.0 --output one-lite.json
agent-bench run swe-bench-lite nexus --env docker \
  --benchmark-config one-lite.json --model-config nexus-model.json \
  --output /tmp/abk-lite-results --prepare-timeout 600 --agent-timeout 900 \
  --verify-timeout 1800 --max-steps 40 --startup-retries 0
```

The official instance image supplies dependencies. Preparation restores its
repository to the task base commit. The Agent receives only problem_statement
and that repository, without hints, reference patch or protected test patch.
A separate official container receives the immutable candidate patch and runs
upstream make_test_spec/run_instance. The sole TestSpec override fixes the image
reference to its digest; the client wrapper adds recovery ownership labels.
No test generation, patch application or F2P/P2P grading is reimplemented.

Only a completed official report with boolean resolved yields PASS or FAIL.
Missing reports, timeout or infrastructure errors yield ERROR. Agent completion,
candidate correctness and cleanup stay separate. Complete official report/logs,
physical executions, candidate hashes and trajectory are retained.

The reference-patch control for psf__requests-1963 passed. Real Nexus acceptance
is tracked in [implementation status](implementation-status.md); this smoke is
not a 300-task score. Upstream dataset and repository licenses apply to task text:
https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite and
https://github.com/SWE-bench/SWE-bench.
