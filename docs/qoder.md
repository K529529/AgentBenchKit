# Qoder CN Harness

QoderHarness uses the public `qodercn-agent-sdk==1.0.15` with the unchanged
Qoder CN CLI **1.1.65**. The Windows command is `qodercn`; the Linux image
contains the official `qoderclicn` executable. AgentBenchKit does not implement
Qoder's inference loop or modify its tools.

## Authentication and model

Log in with the official CLI first. Provide the explicit `.qoder-cn` directory
through `--qoder-auth`; never put credentials in a benchmark config or image.
Only `.auth/user` and `.auth/machine_id` are read as opaque cache files. They
travel through bootstrap stdin into Docker tmpfs, with mode 0600, and are removed
with the container. Global settings, plugins, histories and skills are not copied.
HostProcess is not supported for this authentication mode.

The confirmed model is `Qwen3.8-Flash`, with requested reasoning `low` and output
limit 16,384. Public AssistantMessage events record the returned model identity;
this does not prove a server-side model revision. The account manages its endpoint
and provider. This adapter rejects explicit API endpoints, temperature, top_p,
seed and request timeout parameters that it cannot enforce.

Account runs are `subscription_smoke` and cannot establish formal API comparability
with Nexus/Bailian, even when requested model names look alike. Credits are Qoder
account units, not CNY or a token-price estimate.

## Build and run one task (Linux/WSL)

Prepare the pinned FeatureBench source/data as described in [FeatureBench](featurebench.md).
Build an ABK wheel and obtain the official fixed CLI archive:

```sh
uv build --wheel --out-dir dist
curl --fail --location https://static.qoder.com.cn/qoder-cli-cn/releases/1.1.65/qoderclicn-linux-x64-baseline.tar.gz --output qoderclicn.tar.gz
uv run python -m agentbenchkit.harnesses.qoder_build \
  --image docker.io/libercoders/featurebench-specs_packaging-instance_c393a6a8@sha256:96b12548b35b5983ac1dab9a101b4a49946fceb6a05c97690cd942ff014be916 \
  --tag abk-featurebench-packaging-qoder:v0.2.0 \
  --uv-binary "$(command -v uv)" --cli-archive qoderclicn.tar.gz \
  --wheel dist/agentbenchkit-0.1.0-py3-none-any.whl
```

The builder verifies archive SHA256
`7b28022b3eac5dfd66e4cad78767f91c985ae071a149329042bc21890a4a4876`,
installs the fixed SDK in a separate `/opt/abk` Python environment, and labels
the official base digest and exact driver wheel hash. No login files enter the build.
Use the wheel filename corresponding to the checked-out package version.

```sh
uv run agent-bench make-config featurebench \
  --task pypa__packaging.013f3b03.test_metadata.e00b5801.lv1 \
  --dataset /path/to/featurebench-fast-v1.1.json \
  --official-source /path/to/FeatureBench \
  --evaluator-python /path/to/evaluator-venv/bin/python \
  --agent-image abk-featurebench-packaging-qoder:v0.2.0 \
  --output qoder-featurebench-smoke.json
uv run agent-bench run featurebench qoder --env docker \
  --benchmark-config qoder-featurebench-smoke.json \
  --qoder-auth /mnt/c/Users/YOUR_USER/.qoder-cn \
  --model-config examples/models/qoder-smoke.toml \
  --max-steps 20 --max-credits 10 --agent-timeout 600 \
  --prepare-timeout 1800 --verify-timeout 1800 --startup-retries 0 \
  --output /tmp/abk-qoder-results
```

`make-config` does not execute anything. The final `run` command invokes the model.
Use an ext4 output directory. Keep a single task for implementation smoke;
the frozen 16-task formal experiment is separate.

## Usage monitoring and evidence

Before inference, the public SDK must return an account Credits snapshot. The
worker uses a separate no-query SDK connection to poll the account every 10 seconds,
recording before/during/after snapshots, per-request usage and the final SDK result.
The inference connection can return empty usage snapshots while busy. Empty account
queries are treated as unavailable; the observer never receives the task prompt.
Default controls interrupt at 5 cumulative reported request Credits (deduplicated
by explicit request ID), a 5-Credit account drop, or 2 Credits for one request.
The cumulative threshold can be changed with `--max-credits`; the example uses the
owner-approved 10-Credit retry threshold. Unavailable monitoring
interrupts the execution instead of silently continuing unmonitored.

These are observation-based stop thresholds, not provider-enforced billing caps:
an in-flight request can overshoot, account usage may be delayed, and other sessions
can change the account balance. Preserve both account delta and session-reported
Credits; do not silently equate them. Missing usage stays unavailable.

Official SDK messages, normalized tool calls/results, native call IDs and final
outcome are retained in the redacted trajectory. Complete model inputs are not
exposed. Message IDs are not model-call counts; full call count stays unavailable.
All-zero token placeholders from the managed CLI are normalized to unavailable,
while raw SDK values remain in the evidence. Independent FeatureBench verification uses the pinned official evaluator;
Agent completion and candidate correctness remain separate.

Public references: [CLI usage](https://docs.qoder.cn/cli/usage),
[SDK authentication](https://docs.qoder.cn/cli/sdk/authentication),
[SDK usage](https://docs.qoder.cn/cli/sdk/cost-usage).
See [implementation status](implementation-status.md) for real-run acceptance.
