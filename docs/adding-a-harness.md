# 接入一个新的 Coding Agent

Harness 是 AgentBenchKit 与外部 Coding Agent 之间的 Adapter：将模型配置转换成
Agent 原生配置，描述启动命令，解释公开事件与结束状态。它不实现 Agent 推理循环，
也不负责进程执行、候选冻结或测试判定。可类比 Java 的接口适配层：
`Harness` 是 Protocol，`ModelSpec` 是公共 DTO，Environment 才负责实际执行。

Nexus v0.2.0、Codex 0.155.1 和 Qoder CN 1.1.65 已有 Harness，可直接使用
`agent-bench run micro_swe nexus ...` / `agent-bench run micro_swe codex ...`。
Agent 本体须安装在执行环境中；安装 AgentBenchKit 不会自动安装这些 Agent。
未知 Agent 的命令、认证配置、JSONL 事件和退出语义不同，所以需要新的 Adapter。
**Adapter 应使用公开 CLI/SDK，不应要求修改被评测 Agent 的源码或注入内部埋点。**

## 当前接入位置

V0 采用源码级接入，没有插件管理器、注册装饰器或自动发现 API。

1. 在 `src/agentbenchkit/harnesses/` 增加符合
   [Harness Protocol](../src/agentbenchkit/core/protocols.py) 的类。
2. 先通过 Python 的 [evaluate()](../src/agentbenchkit/runtime/runner.py) 传入实例做 smoke。
   `AgentSettings(harness, model, options)` 会调用它的配置转换方法。
3. 若要通过 CLI 选择它，修改 [cli.py](../src/agentbenchkit/cli.py) 的导入、
   `list_components()` 列表、`run()` 名称校验、实例构造及模型配置分支。
   当前 `run()` 认识 Nexus/Codex/Qoder；不能只添加文件就执行 `run ... new-agent`。
4. 增加对应事件/退出状态/不支持配置的测试，并使用 micro_swe 验证完整链路。
   记录 Agent 版本、认证方式、可观测范围和真实验收限制。

Qoder 的登录缓存、SDK 运行和 Credits 监测见 [Qoder 接入指南](qoder.md)。

## 五个方法的职责

同时声明 `name: str` 和 `capabilities: Capabilities`。
完整字段定义见 [models.py](../src/agentbenchkit/core/models.py)。

| 方法 | 当前签名与职责 |
| --- | --- |
| `native_config` | `(model: ModelSpec, options: HarnessOptions) -> NativeAgentConfig`：纯配置转换；拒绝不支持的显式参数，不读取或保存真实密钥。 |
| `version_command` | `() -> CommandSpec`：描述不调用模型的版本探测命令；Runtime 在选定环境中执行，记录实际 Agent 身份。 |
| `command` | `(task: TaskSpec) -> CommandSpec`：描述公开非交互执行命令，携带 `task.prompt` 和 Agent 阶段预算；只使用 argv，不能拼 shell。 |
| `decode` | `(line: str) -> dict[str, JsonValue] \| None`：解析 stdout 的一行公开事件为 `kind` / `data` 等 JSON 字段；不编造不可观测信息。 |
| `result` | `(process: ProcessResult, events: list[dict[str, JsonValue]]) -> AgentResult`：结合原生终止事件和进程结果，报告 Agent outcome、最终回答及可得 usage；不判定任务正确性。 |

`CommandSpec` 只有 argv 形式，`cwd` 必须留在工作区内，`shell=None`。
版本命令应快速结束，不能需要交互登录。`decode()` 对无法解析的非空行返回 `None` 时，Runtime 会计入解析错误，
正常退出也可能得到 `execution_status=ERROR`。应优先选 Agent 的纯 JSONL 模式；
普通诊断输出应走 stderr。已有 `assistant_delta` / `tool_output_delta` 只进入原生
事件列表，不写入归一化 Event 流。不能通过乱造事件来掩盖损坏协议。

## ModelSpec → 原生配置

模型身份与连接由公共 [ModelSpec](model-contract.md) 表达；不要再创建独立
`NewAgentModelSettings` 与已有 Harness 分叉。`HarnessOptions` 表达 Agent 控制项。

`native_config()` 返回：

- `config_directory`：如 `.nexus` / `.codex`；`config_toml`：启动配置 TOML；Qoder 使用明确标注的 ABK SDK 启动配置。
- `effective_model`：实际生成配置对应的 ModelSpec；只解析已知默认值。
- `credential_env`：密钥环境变量名；`config_home_env`：Agent 特定配置 HOME 变量（可选）。
- `wire_api`：允许 `chat_completions`、`responses`、`chatgpt`、`qoder_managed`。
- `controls`：非模型的有效原生控制项；登录缓存使用可选 `credential_file` 或 `credential_files`（安全相对路径列表）。

公共 `AgentSettings` 负责解析凭据引用、脱敏、每次物理执行建立隔离 HOME 和写入
`<HOME>/<config_directory>/config.toml`。Docker 的配置路径由 Environment 处理。
密钥不能出现在 argv、TOML、manifest 或 stdout；不要读取用户全局配置冒充隔离配置。
不支持的显式字段必须报错，不能默默丢弃；未知默认值保留 null。

当前配置装配支持 TOML、API key、ChatGPT 登录及 Qoder 不透明登录缓存。
若新 Agent 只接受其他配置格式或认证方式，需要单独评审公共契约扩展；
不能在示例中假装这些机制已经存在。

## 原生事件 → 统一 Trajectory Event

`decode()` 返回的不是 `Event` 实例。Runtime 将返回值保存在
`Event.attributes.native`，分配 run/task/sample/physical_execution ID、递增 seq、
时间戳和事件 ID，并将 `source` 设为 `harness.name`。

| decode 返回的 `kind` | Runtime Event.type |
| --- | --- |
| `run_started` / `run_finished` | `agent_started` / `agent_finished` |
| `model_started` / `model_finished` | `model_call_started` / `model_call_finished` |
| `tool_started` / `tool_finished` | `tool_call_started` / `tool_call_finished` |
| 其他公开 kind | 原样保留，不推断其语义 |

若 `data.call_id` 存在，Runtime 设置 `native_call_id`。例如 Nexus 的公开工具输入：

```json
{"kind":"tool_started","data":{"call_id":"call-1","name":"read_file","arguments_json":"{\"path\":\"app.py\"}"}}
```

工具输出与输入不能混为一谈；不要把文件变更结果当成完整工具参数。原生 ID 缺失时
保持 N/A，不能伪造一个 ID 声称它来自 Agent。私有推理与 `protocol_data` 不应输出。

统一事件 envelope 不保证所有 Analyzer 自动兼容新 Agent。
[重复工具调用观察](trajectory-analyzers.md) 识别已有 Harness 的已核实输入形状，
[分析实现](../src/agentbenchkit/analysis/repetition.py) 有来源判断；新增 Agent 必须独立
确认工具输入契约并补充分析支持，否则相关分析应不可用，不能改名冒充 Nexus。

## Capabilities 与 N/A

当前 Capabilities 字段包括 `final_answer`、`tool_calls`、`tool_results`、`model_usage`、
`model_input`、`native_call_ids`、`patch`、`file_reads`，以及三态的 `model_output`
（`available` / `partial` / `unavailable`）。布尔字段表示公开可观测能力，不能证明
每次调用都有完整证据。`patch` 默认 true，表示候选变更可得，不代表工具内部动作可见。

仅在公开接口确实提供该数据时声明支持。例如 CLI 没有完整模型输入，就将
`model_input=False`；只暴露部分最终回答，不能标成完整 `model_output=available`。
缺失 token、工具调用、原生 ID 或价格时，null / N/A 表示“没有测到”；0 表示
“可靠地测得没有发生”。混用会让效率与成本比较产生错误结论。

## Agent outcome 与执行、正确性分离

| AgentOutcome | 需要的证据 |
| --- | --- |
| `COMPLETED` | 公开终止事件明确正常完成，且与该 Agent 的退出码契约一致。 |
| `FAILED` | Agent 明确报告执行失败。非零退出码本身不能证明任务答案错误。 |
| `LIMITED` | Agent 明确报告步数/token 等自身限制。 |
| `ABORTED` | Agent 明确报告主动取消/中止。 |
| `UNKNOWN` | 缺少终止事件、未知状态或证据冲突，不能猜成功。 |

先核实各 Agent 的公开契约，不能统一假设“exit 0 就是 COMPLETED”。
Runtime 另行记录 `ProcessResult.timed_out/cancelled/cleanup_complete` 和
`ExecutionStatus`：框架超时不等于 Agent 自己报告 LIMITED，框架取消也不应伪造
原生 ABORTED。停止确认后才冻结候选，由全新独立 verifier 决定 PASS/FAIL。
所以 Agent COMPLETED 可能候选 FAIL；LIMITED 的候选也可能 PASS，但 sample_success
仍受冻结的端到端语义约束。Harness 不写 verifier/candidate_pass/sample_success。

## 可运行示例与 smoke

[examples/custom_harness.py](../examples/custom_harness.py) 展示最小组合式 Harness：
它接入的确实是 Nexus，复用已测试的 `NexusHarness` 原生映射，显式实现五个方法。
这个示例使用真实 Nexus CLI，并未引入另一个 Agent。`name=nexus` 对应真实来源，
因此保留现有分析支持。换成另一个 Agent 时，必须替换它的配置、命令、事件与结果映射，
并使用该 Agent 自己的名字，不能只改类名或可执行文件名。

先按 [README](../README.md) 准备 Nexus 镜像、公共模型配置和密钥环境变量：

```sh
uv run python examples/custom_harness.py --help
uv run python examples/custom_harness.py --model-config examples/models/nexus-api.toml --env docker --docker-image agentbenchkit-nexus:v0.2.0
```

脚本将真实 Adapter 实例直接传给 `evaluate()`，跑一题 `clamp`。它会调用模型并消耗
配置对应的额度；本地可信开发可显式选择 `--env host_process --executable nexus`。
这条 Python 入口无需 CLI 注册。新增 Agent 的 smoke 也可以照此使用 `load_tasks(("clamp",))`，
再扩大到 `stable_unique` 或八题。不要将受控 fixture 测试说成真实 Agent 验收。

验收时查看新 run：版本探测、manifest 模型与 capabilities、公开轨迹、原生结束状态、
候选冻结、独立 verifier 和清理状态；保留失败记录，核对 missing observability。
凭据缺失/无效事件/结束状态冲突/超时与取消也需要覆盖，不能只检查一条 happy path。

## 后续演进方向（未实现）

未来可评审 Python entry-point / plugin discovery、版本兼容声明以及更通用的配置
文件装配。当前版本不承诺这些 API。
