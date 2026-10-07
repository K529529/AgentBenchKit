# Release hardening: repeated tool calls

评估与验证日期：2026-10-07（Asia/Shanghai）。

## 决定

本次加入 Repeated Tool Call Detection；暂缓 Stagnation Detection。
不修改 Agent、不增加事件采集器、不增加依赖或模型调用。

| 公开证据 | 足够做什么 | 不能证明什么 |
| --- | --- | --- |
| Nexus tool_started 的 name、arguments_json、call_id、step | 同一工具和完整公开参数的重复 | 相同输入执行时 workspace 状态相同 |
| Codex command_execution 的 command、item ID | 公开命令字符串重复 | 全部底层工具参数、隐藏 cwd/env 或模型步数相同 |
| Codex file_change；最终 candidate diff | 一部分修改事实、最终候选差异 | 每一步是否有修改、修改后是否回滚 |

Stagnation 缺少逐步且完整的 mutation 证据：shell 可写文件，最终 diff 为空也可能
经历修改与回滚；长时间读代码、重试命令、运行测试均可能合理。当前不设置停滞
阈值、不输出停滞标签或猜测的 confidence。未来若有完整的逐步快照/修改事件，
再考虑“重复探索 + 连续窗口无修改 + 正常测试排除”的保守规则。

## 重复规则

- 只比较同一 run/sample/physical execution/source 中的调用，不合并重试。
- call ID 将 started/finished 和重复事件折叠为一次调用；冲突输入则跳过。
- Nexus JSON 对象键排序，忽略 JSON 语法空白；字符串、数组顺序、工具名保持原样。
- Codex 只比较完整公开 command 字符串；若公开 cwd/workdir/shell，也纳入匹配。
  不解析 shell、不压缩命令空白、不补默认参数、不把不同工具当作同一个工具。
- 缺失 ID、缺失/损坏参数、重复 JSON 键、非有限数字、已脱敏输入均不强行匹配。
  不支持的工具事件保留为未知间隔，不能把其两侧误报为连续调用。
- 至少两个不同 call ID 才产生 REPEATED_TOOL_CALL，记录 occurrences、repeat_count、
  最大连续次数、连续/间隔模式、可用 step、call ID 与逐事件 evidence_refs。
- consecutive 指“公开工具事件顺序中相邻”，不是并发任务的执行先后保证。
  截断轨迹仅报告已见次数，并标记 PARTIAL；缺少可用输入为 UNAVAILABLE。

重复测试会被如实记录为重复事实，但**不是失败、低效或停滞告警**。
本规则不改变 verifier_status、sample_success、RCA owner/confidence 或质量评分。
实际语义相同但命令写法不同可能漏检；当前宁可保守漏检，也不做危险语义归一化。

## 使用与版本

`agent-bench replay RUN_ID` 创建新 rules-v2 分析，新增
`samples[].trajectory_analysis.repeated_tool_calls`，分析器版本为
`repeated-tool-calls-v1`。原 manifest、轨迹、判定和历史 analysis 保持不变。
新运行的 manifest 标明所用 Analyzer 版本。Viewer 样本页增加只读展示区。

输入不重复拷贝到报告，只保存参数指纹和事件引用；可通过引用检查原始公开输入。
当前只支持已检查的 Nexus/Codex 公共事件形状，新增 Agent 需单独确认输入契约。

## 该阶段的历史验证

- 新增 19 个参数化/集成测试用例，覆盖连续与跨步重复、开始结束去重、正常重测、
  未知/冲突/脱敏参数弃权、物理执行隔离、部分轨迹、原判定及历史分析不变。
- 全套：139 PASS、7 Docker SKIPPED；Ruff、Windows/Linux-target mypy PASS。
  本次不改变容器执行行为，未重跑 Docker 或付费模型；已有真实证据作离线 Replay。
- Nexus 8 题轨迹：66 次可分析、0 次跳过、0 个重复组。
- Codex 成功 2 题轨迹：6 次命令可分析、2 次其他工具事件跳过、0 个重复组。
- Codex 初次失败的 2 题轨迹：无可用工具输入，返回 UNAVAILABLE，不推断停滞。
- 上述 3 次真实 run 的原证据哈希、summary.json 和既有分析文件均未改变。

真实轨迹回放验证兼容性与不变性，重复检测正例来自受控测试；未声称已有真实
停滞样本或统计意义上的低误报率。当前 release 的完整测试与验收状态见 [acceptance](acceptance-v0.md)。
