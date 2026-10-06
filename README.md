# AgentBenchKit

轻量级、本地运行的 Coding Agent 评测工具。用公共 CLI 接入 Nexus / Codex，
在隔离环境运行整个 Agent，冻结候选代码，再用独立测试验证结果。

**执行完成、代码正确、端到端成功是三个不同结论。** 分析和清理失败独立记录；
不可观测指标显示 N/A，不补成零。V0 内置 8 道 Python micro_swe 任务。

[架构方案](docs/architecture-v0.3.1.md) · [公共模型契约](docs/model-contract.md) ·
[验收证据](docs/implementation-status.md) · [已知限制](docs/limitations.md)

## 安装与检查

需要 Python 3.12+、uv；容器评测需要 Docker Engine / Docker Desktop。
Windows PowerShell 和 Linux 均有 CI 检查。

```sh
uv sync --locked
uv run agent-bench --help
uv run agent-bench validate-benchmark
uv run pytest
uv run ruff check .
uv run mypy
```

`validate-benchmark` 验证全部任务的 no-op 应失败、参考候选应通过，不调用模型。
启用真实 Docker 测试：PowerShell 先执行 `$env:ABK_TEST_DOCKER='1'`，
Linux 则执行 `ABK_TEST_DOCKER=1 uv run pytest`。

## 构建 Agent 镜像

```sh
uv run python scripts/build_nexus_image.py /path/to/Nexus-next
uv run python scripts/build_agents_image.py
```

第一条从本地 Nexus Git 仓库导出固定 v0.2.0 提交；第二条使用 GitHub CLI
下载完整官方 Codex 0.155.1 Linux 包。脚本不修改 Agent 源码，不复制个人配置。
本机需有 Git、GitHub CLI 和网络访问能力。

## 显式 Model / Provider 评测

复制并调整 `examples/models/nexus-api.toml` 或 `codex-api.toml`，
在当前终端设置配置引用的密钥环境变量。模型文件只保存凭据引用。

```sh
uv run agent-bench run micro_swe nexus --env docker --docker-image agentbenchkit-agents:v0 --model-config examples/models/nexus-api.toml --samples 1 --concurrency 2
uv run agent-bench run micro_swe codex --env docker --docker-image agentbenchkit-agents:v0 --model-config examples/models/codex-api.toml --task clamp --task stable_unique
```

Codex API 示例中的 `REPLACE_WITH_MODEL_ID` 必须替换为 Provider 实际支持的模型。
两个 Harness 都使用公共 `ModelSpec`，分别转换为 Agent 原生配置；每次执行使用
独立 HOME / CODEX_HOME。不支持的显式参数直接报错，详见[模型契约](docs/model-contract.md)。
Nexus 的 `--nexus-config /path/to/config.toml` 保留为兼容导入入口。

`--agent-timeout`、`--prepare-timeout`、`--verify-timeout` 和 `--overall-timeout`
控制阶段预算；`--samples` 是每题采样数，`--k` 控制 pass@k。
`--startup-retries` 仅在 Agent 开始前重试基础设施，物理执行记录全部保留。
运行过程中打印每个样本的执行/Agent/验证状态，结束后返回 run ID。

## Codex ChatGPT 登录 smoke

```sh
uv run agent-bench run micro_swe codex --env docker --docker-image agentbenchkit-agents:v0 --model-config examples/models/codex-smoke.toml --codex-auth /path/to/.codex/auth.json --task clamp --task stable_unique
```

仅用于接入验收。登录缓存经 stdin 进入容器 tmpfs，不写入镜像或结果目录。
记录标为 `subscription_smoke`；不能据此宣称正式 API 或同模型公平比较。
运行会消耗对应账号的模型额度。

## 查看、重放和比较

```sh
uv run agent-bench runs
uv run agent-bench view RUN_ID
uv run agent-bench replay RUN_ID
uv run agent-bench compare BASELINE_RUN CANDIDATE_RUN
uv run agent-bench recover
uv run agent-bench rebuild-index
```

结果默认在 `.agentbenchkit/results`。Viewer 只监听 `127.0.0.1:8765`，只读展示
任务、轨迹、候选 diff、独立验证证据、指标、归因及可比性限制。
SQLite 仅是可重建索引，文件证据是事实来源；重建损坏索引会保留损坏文件副本。

Replay 生成新 analysis ID，不覆盖历史记录。Compare 先比较 manifest 条件；
非预期差异或未知结果产生 INCONCLUSIVE。`--expect harness` 等参数用于声明
实验变量，不能消除订阅认证、未知模型参数等可比性限制。

## 可选质量 Judge

```sh
uv run agent-bench judge RUN_ID SAMPLE_ID --model JUDGE_MODEL --endpoint https://api.example.com/v1 --key-env JUDGE_API_KEY
```

这会把该样本的限量任务/代码/公共轨迹发送给指定 Provider，并单独计入 Judge
usage。四个质量维度为测试质量、工具使用、解法质量、效率；缺少证据时 N/A。
Judge 不修改 verifier 或 sample_success，每次输出独立版本。真实在线 Judge
尚未验收；受控 HTTP、超时、失败隔离与版本保留已测试。

## 边界

Docker Agent 容器有 CPU/内存/进程限制；全新 verifier 禁用网络、测试资产只读。
`host_process` 仅用于可信本地调试，不是文件系统沙箱。V0 不面向恶意 Agent，
Agent 能访问自己执行所需的模型凭据，建议使用专用评测密钥。

二进制文件、符号链接与 Windows junction 候选暂不支持，会明确失败。
Windows bind mount 不声称保留 Linux 可执行位。模型价格未固定时 cost=N/A。
当前 micro_swe 结果不是 SWE-bench 官方分数，8 道小题也不是能力排行榜。

采用 [MIT](LICENSE) 许可证。第三方 HTMX 许可证随静态文件保留。
