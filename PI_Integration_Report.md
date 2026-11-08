# Pi Harness 接入与单题闭环验收报告

更新：2026-11-08（Asia/Shanghai）。项目：`D:\WorkSpace\AgentBenchKit`，分支 `feature/V0.2.0-implementation`。

**结论：Pi 1.4.0 + DS Flash 的真实单题闭环已跑通，官方独立验证 PASS。** 用户最新指令将本轮收窄为“确认链路通即可”；3 题 Pilot 与大规模评测暂缓，没有创建云主机、提交或推送 Git。

## 1. 接入变更与不变边界

新增 `src/agentbenchkit/harnesses/pi.py`、`pi_worker.py`、`tests/test_pi.py`、`docs/pi.md`、`examples/models/pi-deepseek-flash.json`；CLI 注册 `pi`、`--pi-python`、`--pi-executable`。复用 Nexus/Codex/Qoder 所遵循的 Harness 接口，进程和工作区仍归 Environment/Runtime 管理。

没有修改 Pi 源码，也没有修改 ABK Benchmark、Runtime、Candidate Freeze、Official Verifier 或指标定义。原有 SWE-bench 文件修改和历史 `ABK_Evaluation_Report.md` 保留，均不是本次变更。

模型配置、字面任务输入、工具调用 ID、最终消息 Usage、完成/超时/取消/异常终态已接入。只在 `agent_settled`、assistant 正常 stop、退出码 0 且输出未截断时判 COMPLETED；provider error 或协议不完整保持 UNKNOWN/ERROR。Agent 正常完成后由官方 verifier 决定 PASS/FAIL。

## 2. 固定身份、预算与环境

- Pi：`@earendil-works/pi-coding-agent@1.4.0`，使用公开 `--mode json --print` CLI。
- Node：22.16.0，运行时基础镜像 digest `sha256:048ed02c5fd52e86fda6fbd2f6a76cf0d4492fd6c6fee9e2c463ed5108da0e34`。
- 请求及 Pi 返回 model：`deepseek-flash`；provider `deepseek`；endpoint `https://api.deepseek.com`。公开别名对应的后台权重不是客户端可冻结的 digest。
- reasoning=off，通过 DeepSeek 公开参数 `thinking.type=disabled` 明确关闭；最终 Usage reasoning=0。context_window=1,000,000，max_output_tokens=8192。
- 禁用扩展/MCP、skills、prompt templates、context files、持久化 session、自动 retry、compaction、cache warming；隔离 agent home，项目 `.pi` 存在时拒绝执行。
- Pi CLI 不支持可保证的步数/credit 上限，显式拒绝 max_steps/max_credits，而非默默忽略。采用 agent=900 秒墙钟预算；单请求输出限制不等于总费用硬上限。
- 阶段预算 prepare=1800s、agent=900s、collect=180s、verify=1800s、analysis 默认60s、cleanup=60s；并发1，startup_retries=0。
- 推理容器 4 CPU / 8192 MiB / 512 PID；prepare/verifier 沿用官方环境，不能把推理限制误当作整个任务的资源上限。
- 官方数据 revision：`76b4a4566e04f4bcc13c35125d4f301791efa736`；evaluator commit：`8d4e347ec57546685c5a87e8676bf575db022ea6`，未改动。
- 成功 Smoke 推理镜像：`abk-pi-mlflow:1.4.0-20261108-r3`；不可变 ID：`sha256:e95494b17e92f1d4c12c44c71b8d7966cd502c2438a3510e00a033a011a9e05d`；逻辑镜像大小 13.29 GiB（共享层计入，不是本次新增物理空间）。
- 官方基础镜像：`docker.io/libercoders/featurebench-specs_mlflow-instance_efffa87e@sha256:5a63b594bc99a6dcd876289974979606b276edd49e966020111db3590c40add4`。

镜像复用已有隔离的 Nexus v0.3 层，保留额外 Nexus 依赖，尚不是最小 Pi 镜像。顶层 Pi 版本固定、依赖封存在镜像内；完整依赖锁/SBOM 是后续可复现交付事项。

## 3. 所有尝试，分别计数

同一个独立任务，共4条物理执行记录：

| Run ID | Agent 启动 | 结果 | 审计口径 |
|---|---:|---|---|
| `20261107T103315Z-8becdee5` | 否 | PREPARE 宿主中断 | WSL 崩溃，不是模型失败 |
| `20261107T172036Z-04c34002` | 否 | PREPARE 宿主中断 | Windows 事件2004虚拟内存不足，随后 WSL/service 崩溃 |
| `20261107T173026Z-4e0996cd` | 是 | ERROR/UNKNOWN；官方 PASS | 网络包装脚本失效、输出截断；主动终止，不能作为合格验收 |
| **`20261107T173812Z-e8667261`** | **是** | **FINISHED / COMPLETED / PASS** | **合格单题闭环** |

前三条不能隐去，也不能混入最后一条的成功率分母。成功验收配置下 Candidate Pass Rate=1/1、Sample Success Rate=1/1；全部4次物理尝试中只有1次满足完整验收条件。只有1道独立题，不支持任何普遍性能力结论或 Benchmark 排名。

第三条虽 verifier PASS，但执行协议不完整，sample_success=null；原始 candidate_pass=true 保持不变，报告单独排除该次作为验收依据，没有重写历史指标。

## 4. 成功单题的真实执行

Task ID：`mlflow__mlflow.93dab383.test_trace_correlation.53c200a6.lv1`，来自固定 FeatureBench Fast 16题 Evalset。

Physical execution ID：`e9663a610c514e48bd99f7e2686857ee`。
本地时间约 2026-11-08 01:38–01:42；Run ID 使用 UTC 日期。

Pi 阅读任务工作区的接口、analytics 模块和调用方，随后编写 NPMI 相关实现并补充导出。收集到两个修改文件：

- `mlflow/store/analytics/trace_correlation.py`
- `mlflow/store/analytics/__init__.py`

候选冻结后，官方 verifier 在独立容器中应用补丁。最终 resolved=true：**FAIL_TO_PASS 21成功/0失败，PASS_TO_PASS 30成功/0失败**。这是从官方 tests_status 列表计数；ABK 通用 tests_executed 等字段仍是 null，不能混淆两者来源。

执行退出0，timed_out=false，cancelled=false，output_truncated=false，cleanup_complete=true；execution errors=[]，candidate_frozen=true，sample_success=true。分析器/LLM Judge 未参与正确性判定。

## 5. 资源与 Token：真实读数及局限

| 指标 | 单题结果 | 口径 |
|---|---:|---|
| Agent 进程耗时 | 24.799秒 | execution.process.duration_ms |
| 完整 evaluate 墙钟 | 268.798秒（约4.48分钟） | 实验驱动外层 time.time；含准备、执行、收集、验证、清理 |
| ABK execution duration | 271.674秒 | Runtime 自身单调时钟记录；与外层口径不同，分别保留，不强行改成同值 |
| 模型调用/步数 | 7 / 7 | assistant message_end / turn_start |
| 工具调用 | 6 | tool_execution_start |
| 未缓存输入 | 7,115 Token | Pi usage.input |
| 缓存读取输入 | 39,040 Token | Pi usage.cacheRead，不能再次计入未缓存输入 |
| 输出 | 2,472 Token | usage.output |
| 总计 | 48,627 Token | 三项之和；cacheWrite=0、reasoning=0 |
| 推理容器采样内存峰值 | 1,247.11 MiB | cgroup memory usage，含缓存，不等同 RSS；12个样本 |
| 推理累计 CPU | ≥9.384 CPU秒 | 最后观测到的累计量，容器退出前可能有未采到的尾段 |
| prepare 容器内存峰值/CPU | 1,480.59 MiB / ≥29.214 CPU秒 | 26个样本，不包含 Docker daemon 的 commit 开销 |
| verifier 容器内存峰值/CPU | 2,372.46 MiB / ≥40.076 CPU秒 | 25个样本；约2秒采样，短峰可能漏采 |
| 冻结运行证据体积 | 1,017,287 bytes | 原始 run 目录；不含额外解包事件、资源采样副本与共享镜像 |
| 清理后 Linux 空闲空间差 | 2,904,064 bytes | 外层 free_disk_delta；受其他写入影响，不是峰值磁盘占用 |
| 任务磁盘峰值/主机整体内存峰值 | N/A | 本次没有可靠连续记录，不能用容器内存替代 |

快照阶段曾使 Windows 可用提交内存降至约3 GB；期间执行 sync 和 drop_caches 释放已落盘文件缓存。该人工干预以及本地镜像缓存状态，使此次时延不是标准性能基线。

Pi 自定义模型的 cost 字段全0，不代表免费。按2026-11-08读取的[DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing/?model_version=DeepSeek-V4-Pro-0813)，非高峰每百万未缓存输入/缓存输入/输出为 $0.15/$0.003/$0.60；成功这一条估算 **$0.00266757**，高峰对应 **$0.00533514**。这是 Token×公示单价，不是账单核对结果；不含第三条故障运行的费用（其完整 Token 因截断不可恢复），也不含机器、电力、存储、网络费用。

## 6. 实测发现并修复的问题

1. **宿主内存压力**：先临时关闭 WSL GUI 并重启仍未解决；Windows 事件2004证实虚拟内存不足。用户清理后台进程后，本轮得以完成；没有应用4GB memory/8GB swap方案，未擅自关闭用户其他应用。
2. **网络包装器 CRLF**：Windows生成的 shebang 含CRLF，在 Linux PATH 查找时未按预期使用包装脚本，导致第三条推理落到 bridge。已改为 LF，并在真实推理前创建探针容器核对 network mode，成功运行实际网络为 `abk-pi-20261108-r3`。
3. **Pi JSON 事件超过2 MB传输上限**：第三条输出被截断。启动器现在消费官方 CLI，完整脱敏事件以 gzip+base64 归档块进入持久化 stdout；流增量与重复 agent_end 数组不再重复占用普通事件通道。最后一条 stdout 169,813 bytes，完整原始事件2,400条，可无损解包；最终消息/工具事件保留原协议形状。
4. **DS 默认思考模式**：只设置 Pi reasoning=false 不足以显式禁用 DeepSeek 默认思考；已补充公开 samplingParams 中的 thinking.disabled，成功运行实际 reasoning=0。
5. **ABK分析器终态 Usage 接口**：成功运行后补齐 `abk_summary`，向现有 run_finished.data 导出 usage/steps/model_calls；没有改统计公式。用成功运行的2,400条真实事件离线回放，核对48,627 Token、7调用/7步。

**版本边界必须保留：最后一项统计桥接是在真实 PASS 后追加的，仅做了真实事件离线回放和回归验证，没有再调用模型。成功镜像冻结的是桥接前版本，原始历史事件未补写；后续正式实验需重建最终源码镜像。** 当前报告的 Token 数由该次原始 message_end 直接计算，不能声称旧运行的 ABK replay 自动字段已经补齐。

## 7. 网络、防污染、异常与清理

成功运行使用 internal Docker network，加只允许 api.deepseek.com:443 的 CONNECT＋TLS SNI 代理。探针记录 DeepSeek 401、GitHub/PyPI DENY、直接IP失败；真实调用有 ALLOW 日志，推理容器 network mode 已核实。该网络是本次实验包装器实施的外部控制，Runtime environment.json 的配置值 bridge 不能替代实际容器/网络回执。

完整成功轨迹未出现外部下载、复制参考实现或读取系统缓存实现的行为。任务初始化使用官方 mask 过程；检查了实际工具调用和 patch，但未对所有镜像层、所有缓存文件做穷尽性静态证明。结论是“未观察到参考实现污染”，不是“保证零污染”。第三条截断且网络开放的运行不具备同等可信度。

真实 Docker timeout/cancel 控制检查均通过：进程返回137，分别 timed_out/cancelled=true，cleanup_complete=true，终止后 beat 文件不再变化。它们是无模型的生命周期测试，不计入 Benchmark 样本。协议错误/缺失终态/截断亦有单元测试。首次控制夹具因验证工作区默认只读无法写 beat，修正夹具为可写后通过，未改产品隔离默认值。

Runtime 成功清理推理和验证容器；本轮代理及专属网络已删除。历史中断记录、候选、轨迹、验证产物和镜像保留。WSL 配置文件已从备份原样恢复（SHA256一致），**下次 WSL 重启生效**；为避免再次打断其他会话，收尾没有再重启 WSL。

## 8. 测试与交付证据

完整回归：**248 passed、16 skipped**，Ruff 和 strict mypy 通过。最终统计桥接及其断言追加后定向 Pi 测试7 passed、静态检查通过；真实事件离线回放通过，0次新模型请求。16 skipped 为既有 opt-in 测试，不算通过；额外的两项 Docker 生命周期控制已独立实测。

关键路径（均相对于项目根目录）：

- `.agentbenchkit/pi-20261108-r3/evidence/runs/20261107T173812Z-e8667261/`：成功运行的 manifest/plan/summary、sample/verifier、patch.diff、candidate_manifest、execution、trajectory、stdout/stderr 和官方测试日志。
- `.agentbenchkit/pi-20261108-r3/native-events.jsonl`：由归档块解包的2,400条原始脱敏Pi事件。
- `.agentbenchkit/pi-20261108-r3/audit-summary.json`、`evidence/resources.jsonl`、`evidence/executions.jsonl`：指标与原始资源数据。
- `.agentbenchkit/pi-20261108-r3/build/`：成功镜像构建日志、源码快照/hash和镜像ID。
- `.agentbenchkit/pi-20261108-r3/network/`：网络脚本、预检、实际创建回执、proxy.log。
- `.agentbenchkit/pi-20261108-r3/lifecycle-checks.json`、`usage-replay-check.json`、`cleanup-receipt.json`：额外验证与清理。
- `.agentbenchkit/pi-20261108-r2/evidence/`：第三条接入故障的全部存活证据。
- `.agentbenchkit/pi-20261107/interrupted-smoke-evidence/`、`.agentbenchkit/pi-20261108/interrupted-smoke-evidence/`：前两次主机中断；对应 host-crashes/host-memory-events 保留。

不在报告或配置中保存密钥。模型凭据通过环境/stdin传递，原始事件在压缩前先脱敏。

## 9. 50/100题时间与成本：仅机械外推

只按这道较短任务、串行、已有镜像缓存计算：50题约 **3.73小时**，100题约 **7.47小时**；成功单题的模型费用外推为50题 **$0.133–0.267**、100题 **$0.267–0.534**（非高峰至高峰）。

这些数值**不是正式实验预算承诺**：只有一题，无跨仓库分布，未包含失败重试、900秒预算耗尽、首次镜像构建/下载、云CPU/RAM/磁盘/流量和宿主恢复。本轮故障运行费用也不包含在成功单题外推中。不能拿该样本推断全Fast任务耗时或费用。

云端正式预算仍 N/A；没有选型或购买云主机。后续应先用3–5题跨镜像 Pilot 建立时延/Token分位数，分别测 prepare、commit、agent、verify、清理和磁盘峰值，再报价并获确认。单次成功中最大被采样容器约2.32 GiB，但 Docker daemon 镜像快照的宿主开销更大，不能据此宣称4GB云主机足够。

## 10. 后续启动条件

当前验收目标已经满足：真实 Pi → DS Flash → 工具与代码修改 → Candidate Freeze → 官方独立 PASS → 轨迹及报告 → 清理。

按用户最新指令，Pilot和正式实验均暂缓。迁移前仍需：重建包含最终统计桥接的镜像；补全锁文件/供应链证据；把实验网络包装器纳入可复现部署；进行跨仓库Pilot、故障恢复和污染扫描；验证受限云环境下资源峰值；提交包含失败重试与存储成本的预算。未得到额外授权前不创建云资源，也不启动50/100题任务。
