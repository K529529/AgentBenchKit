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

正式隔离执行使用 Docker（需运行 Docker Desktop / Docker Engine）：

```sh
uv run python scripts/build_nexus_image.py /path/to/Nexus-next
uv run agent-bench run micro_swe nexus --env docker --nexus-config /path/to/config.toml
```

构建脚本从现有 Nexus 仓库导出固定 v0.2.0 提交，不修改其源码。
Agent 容器有 CPU、内存和进程数限制；验证容器禁用网络，测试目录只读。
V0 面向可信评测任务：Agent 进程仍能访问自身模型凭据，并非恶意 Agent 的密钥隔离设施。
通常应使用专用低权限评测密钥；本轮实测沿用现有配置已获用户明确授权。

Docker 集成测试需显式设置 `ABK_TEST_DOCKER=1`，未启用时标记为 SKIPPED。
