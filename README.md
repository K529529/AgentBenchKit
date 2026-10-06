# AgentBenchKit

面向 Coding Agent 的轻量级本地评测基础设施。通过外部 CLI 接入 Agent，
独立验收候选代码，区分执行成功、候选正确性和分析状态。

开发契约：[V0.3.1](docs/architecture-v0.3.1.md)。
交付证据：[实施状态](docs/implementation-status.md)。

```sh
uv sync
uv run agent-bench --help
uv run pytest
uv run ruff check .
uv run mypy
```

Python 3.12+。当前处于分阶段实现中，尚未宣称 V0 验收完成。
测试结果与真实 Agent 集成证据分别记录；IDE、密钥和本地评测结果不提交。

首个真实闭环已实现：`micro_swe` 两道任务 → 外部 Nexus CLI → 冻结完整候选 →
全新工作区独立测试 → 本地 JSON/Markdown 证据。

```sh
uv run agent-bench list benchmarks
uv run agent-bench validate-benchmark
uv run agent-bench run micro_swe nexus --env host_process --samples 1 --nexus-executable /path/to/nexus --nexus-config /path/to/config.toml
```

`host_process` 仅用于可信本地开发。运行结果默认存入 `.agentbenchkit/results`。
Nexus 使用临时独立 HOME，按配置中的 `api_key_env` 显式注入密钥；不会修改 Agent 源码。
