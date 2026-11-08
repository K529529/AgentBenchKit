# Pi Harness（固定 1.4.0）

原生适配器调用公开 `pi --mode json --print` CLI，不修改 Pi 源码。支持 API ModelSpec、隔离配置、字面任务输入、工具调用关联、最终消息 Usage 和终态解析；环境继续负责 cwd、超时、取消和进程树清理。

## 使用

安装 `@earendil-works/pi-coding-agent@1.4.0`，并确保执行环境中能找到 `pi` 与包含 ABK 的 Python。Linux/Docker 默认 Python 为 `/opt/abk/bin/python`；本地运行可用 `--pi-python` 明确指定。FeatureBench 必须使用 Linux/WSL Docker。

```sh
agent-bench run featurebench pi --env docker \
  --model-config examples/models/pi-deepseek-flash.json \
  --benchmark-config /absolute/path/to/selected-featurebench.json \
  --agent-timeout 900 --prepare-timeout 1800 --verify-timeout 1800 \
  --startup-retries 0 --concurrency 1
```

通过环境变量 `DEEPSEEK_API_KEY` 提供密钥，不写入配置。Benchmark 配置必须明确选题、固定官方数据/评测器、官方镜像 digest，以及包含 Pi 和 ABK 的推理镜像；官方验证继续使用独立环境。可用 `agent-bench make-config featurebench --task ...` 创建单题配置。

## 协议与边界

- `agent_end` 不是最终完成证据。只有 `agent_settled`、最终 assistant `stopReason=stop`、退出码 0、输出未截断才能得到 COMPLETED。
- API/provider error、缺失终态、异常退出保持 UNKNOWN，由 Runtime 报 ERROR；不能当作 Agent 解题失败。正常完成后的官方 FAIL 才说明候选未通过验证。
- 超时为 LIMITED，取消为 ABORTED；Runtime 的 TIMED_OUT/CANCELLED 仍有独立优先级。
- Usage 仅累加 `message_end` 中 assistant 的最终 usage，不累计 streaming snapshots 或 `agent_end.messages`。缺失字段为 N/A；`input_tokens` 是 Pi 的 input，cacheRead 单独列出，成本计算不可再次把 cacheRead 当作未缓存输入。
- `max_output_tokens` 映射到自定义模型 maxTokens；思考等级传入公开 `--thinking`。不支持的 seed、单请求 timeout、max_steps/max_credits 会明确拒绝，不能默默忽略。墙钟预算不等于美元硬上限。
- 关闭扩展（含内置 MCP）、skills、prompt templates、context files、session persistence、自动重试、自动 compaction、cache warming。发现任务根目录已有 `.pi` 时拒绝启动，防止项目配置覆盖隔离配置。
- 配置启动器消费公开 CLI 子进程输出，环境管理整个进程树；完整脱敏事件压缩归档进入持久化 stdout，避免流增量耗尽传输上限。密钥仅以 `$ENV_NAME` 引用写入 models.json。
- Harness 本身不实现网络沙箱。正式运行必须使用经过验证的 Docker 出站隔离；`HTTP_PROXY` 环境变量本身不构成访问控制。

## 2026-11-08 实测状态

真实 FeatureBench 单题 Smoke `20261107T173812Z-e8667261` 已通过：FINISHED / COMPLETED / 官方 PASS / cleanup COMPLETED。21/21 FAIL_TO_PASS、30/30 PASS_TO_PASS；Agent 24.799秒，48,627 Token。此前两次主机中断和一次网络/截断接入故障全部保留，不混作能力成绩。

统计终态桥接在该次 PASS 后追加，以完整真实事件离线回放验证，未新增模型调用；正式部署须重建最终源码镜像。按用户最新指令，Pilot 暂缓。详细边界与证据见根目录 PI_Integration_Report.md。

公开协议：[Pi JSON events](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/json.md)、[CLI](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/cli.md)、[Models](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/models.md)。
