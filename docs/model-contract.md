# Model 与 Harness 的公共边界

第二个真实 Agent 接入时引入 `core.models.ModelSpec`，替代运行时依赖
`NexusSettings` 的方式。只有一套公共模型配置契约和一个 `AgentSettings`。

```text
ModelSpec + HarnessOptions
    → Harness.native_config()
    → NativeAgentConfig
    → AgentSettings（解析凭据引用、生成独立配置 HOME）
    → Environment（启动整个 Agent）
```

`ModelSpec` 描述模型 ID、Provider ID、显式 endpoint、凭据引用、上下文窗口、
输出上限和可选生成参数。凭据只保存环境变量名，不保存密钥。
`HarnessOptions` 与模型分离，承载循环步数和原生传输选项。
Harness 构造函数不持有模型名或 Provider；转换函数负责兼容性检查。

可以类比 Java：`ModelSpec` 是公共不可变 DTO，`Harness.native_config` 是适配器，
`AgentSettings` 是公共配置装配逻辑。不要在适配器内部再维护一份独立模型 DTO。

## 请求条件与生效条件

schema v2 manifest 的 `requested_model` 和 `model` 均由 Pydantic 验证。
前者保存请求，后者保存适配器解析原生默认值后的配置；`agent_config` 保存
原生 TOML、协议、隔离 HOME 策略和 Agent 控制条件。
“生效配置”表示写给 Agent 的配置，不代表能够验证服务端路由或服务端默认值。
未知字段保持 null，不能猜成 0、false 或一个共同默认值。

旧 schema v1 证据不改写。读取和比较旧记录时，缺少 typed model 条件会产生警告。

| 条件 | Nexus v0.2.0 | Codex 0.155.1 |
| --- | --- | --- |
| 显式模型/Provider/endpoint/密钥引用 | 支持 | 支持 |
| 协议 | Chat Completions | Responses |
| context_window / reasoning_effort | 原生配置映射 | 原生配置映射 |
| max_output_tokens | 支持，默认 8192 | 请求此参数时拒绝 |
| request_timeout_seconds | 支持，默认 120 | 无等价控制，请求时拒绝 |
| temperature / top_p / seed | 当前固定版本拒绝 | 当前固定版本拒绝 |
| ChatGPT 登录 | 不支持 | Docker tmpfs，仅 smoke |

拒绝不支持的显式参数发生在读取凭据和启动 Agent 之前，不能静默丢弃。
同一公共配置可以供两种 Harness 转换，但必须在双方支持能力的交集内；
协议、Agent 内部策略和不可控制的默认值仍可能不同。

## 配置与隔离

`--model-config` 接收公共 JSON/TOML；示例在 `examples/models/`。
Nexus 的 `--nexus-config` 只是兼容导入入口，先转换成 `ModelSpec`，不再有独立
`NexusSettings`。配置文件与 CLI 模型覆盖项不能混用。

每个物理执行有新的 HOME；Codex 额外设置独立 CODEX_HOME。
不载入个人 Agent 配置。API key 通过执行环境注入，Docker 通过 stdin bootstrap
传入，避免写进 Docker inspect 的环境或命令行。ChatGPT 登录缓存仅写入容器
`/agent-private` tmpfs，不写入镜像或结果目录。

`evaluation_class=subscription_smoke` 的记录不得用作正式 API 可比评测。
`explicit_api` 也不是可比性证明：比较须检查模型、协议、原生控制项、任务、
环境及未知生成条件。报告单独标记 `formal_comparable`，不能用 `--expect` 消除
订阅认证或未知模型条件的限制。样本分数变化只是观测，不是能力因果结论。

Codex 显式 API 配置的转换与拒绝逻辑经过自动化测试；真实 API 模型在线验收
尚未运行；现有真实 Codex 验收是 ChatGPT 登录 smoke。


## 已支持 Agent 的运行方式

这些命令使用现有 CLI 接入，不需要新增 Adapter。先按 [README](../README.md)
构建 `agentbenchkit-agents:v0` 并设置模型配置引用的密钥环境变量。
API 配置示例中的 `REPLACE_WITH_MODEL_ID` 必须替换为 Provider 支持的模型。

```sh
uv run agent-bench run micro_swe codex --env docker --docker-image agentbenchkit-agents:v0 --model-config examples/models/codex-api.toml --task clamp
uv run agent-bench run micro_swe codex --env docker --docker-image agentbenchkit-agents:v0 --model-config examples/models/codex-smoke.toml --codex-auth /path/to/.codex/auth.json --task clamp --task stable_unique
```

第二条使用现有登录缓存，会消耗账户额度，结果标记为 `subscription_smoke`。
凭据只经内存通道写入容器 tmpfs，不应复制到仓库或镜像。HostProcess 不支持这种认证。

新增 Agent 的开发流程见 [Adding a Harness](adding-a-harness.md)。未来 plugin discovery
尚未实现。Optional Judge 有独立请求配置与 usage，严格输出和框架版本归属见
[Judge 契约](judge-diagnostics.md)；其真实验收已通过，不改变以上 Agent 模型可比性边界。
