# sh-agent 三题实验：结果与证据

日期：2026-10-11。基于 ABK `v0.2.0`，分支
`codex/sh-agent-c08-c17-c13`。实验保留 sh-agent 原始 Python 源码、提示词、图和工具。

## 模型核实

上游固定版本 `26130e96732c51d83a7ece1d06325216831ee028` 的默认模型是
`deepseek-v4-flash`，通过 `config/settings.yml` 配置，并非只能使用该模型。
现有渠道对这个精确 ID 返回 404 `model_not_found`。经用户明确选择，实际实验
仅将模型配置改为 `deepseek-v4.1-flash`，保留温度 0.1；响应元数据也报告该 ID。

## 最终结果：三个指定任务均未解决

| 任务 | Agent 时间 | 模型调用 | 已开始的工具调用 | 候选 | 官方结果 |
| --- | ---: | ---: | ---: | --- | --- |
| C08 / MLflow | 900.83 秒 | 9 | 20（19 返回） | 空补丁 | FAIL |
| C17 / xarray | 86.30 秒 | 14 | 29 | 空补丁 | FAIL |
| C13 / seaborn | 229.28 秒 | 14 | 30 | 空补丁 | FAIL |

C17、C13 都以 `GraphRecursionError` 结束，错误指向默认递归上限 25。
工具轨迹只有列目录、glob、grep、read_file，没有写入或修改文件调用。
三题官方 evaluator 均已完成并返回 `resolved=false`；空补丁分支没有实际执行测试套件，
不能将其描述为若干测试用例失败。900 秒的 Agent 总时限没有在这两题触发。

C08 达到 900 秒总时限，ABK 记录 TIMED_OUT / Agent outcome UNKNOWN，
候选冻结后官方判定 FAIL。模型最后一次响应后没有再推进；两个根目录搜索
中的 glob 调用到终止时仍未返回。不能把 UNKNOWN 写成正常完成。
本次三个指定任务的 resolved 为 0/3；额外两次模型启动前的准备中断单列保留。

逐次响应完整记录的 token 汇总：C08 输入 416,688 / 输出 7,416；C17 输入 1,108,342 / 输出 5,129；
C13 输入 570,307 / 输出 22,709。输入含重复上下文；缓存细分和账单成本不可得。
基础 Viewer 的可观测性声明保守保留 token N/A，上述数值来自实验报告对原始
callback usage 的汇总，不冒充终止事件中不存在的聚合字段。

## 行为与工程分析

**观察事实：**

- C17/C13 在只读探索阶段耗尽递归预算，最终没有产生候选改动。
- C08 轨迹出现 `glob_files(pattern='**/trace_correlation.py', workspace_dir='/')`
  和 `grep(pattern='calculate_npmi', workspace_dir='/', glob='*.py')`，
  两个调用持续扫描整个容器，CPU 约一个核满载。
- 工具中的 `workspace_dir` 可由模型提供；路径检查以该参数为边界，因此 `/`
  会被接受。`glob_files` 和无 rg 时的 Python grep 回退路径没有硬超时。
- 镜像没有 `rg`。离线复现发现 Python grep 回退中传入文件路径会返回“无匹配”，
  传目录则能找到同样内容。工具描述要求目录，而模型多次传了文件路径。
- YAML 的 `max_explore_files=5` 和 `max_tool_calls_per_turn=10` 没有被执行代码读取。
  配置文件里有数字，不代表运行时存在相应预算。

**推断与边界：**

探索终止条件、工具参数契约与工具执行边界是本次值得优先检查的工程问题。
上述证据不能证明某一个问题是全部失败的唯一原因，也不能直接评价 DeepSeek
模型的通用编码能力。未修补上游、未提高递归上限、未追加修复轮次验证反事实。

## 环境中断与恢复

C08 在真正进入模型前，发生了两次独立的准备阶段尝试：

1. `20261011T091039Z-02ff7205`：WSL 重启，恢复为 INTERRUPTED；未调用模型。
2. `20261011T092054Z-5cfe17d3`：低内存保护中断，PREPARE ERROR；未调用模型，清理完成。

两次均保留原始证据，不能记为 Agent 解题失败，也不能从物理执行记录中删除。
用户分别明确授权了后续 C08 准备尝试。后续真正执行顺序为 C17 → C13 → C08；
顺序变化由基础设施中断引起，不由模型结果决定。

当时 Windows 内存压力确实很高；后续测得 WSL 约 13 GiB 为文件缓存、进程实际
使用约 1.2 GiB。同步磁盘并释放可回收缓存后，Windows 可用物理内存恢复约 10 GiB。
首次 WSL 重启的唯一原因仍未确定。没有关闭用户应用或修改全局 WSL 配置。
后续运行记录了缓存回收及内存保护，时间不能直接与无此干预的旧运行作因果比较。

## 协议与证据

- 每题真正 Agent 执行一次；900 秒 Agent 总预算；无模型结果后的重跑/换题/人工修补。
- 数据集 `76b4a4566e04f4bcc13c35125d4f301791efa736`；官方 evaluator
  `8d4e347ec57546685c5a87e8676bf575db022ea6`；原始官方测试语义不变。
- WSL ext4 工作区、串行执行、独立官方 verifier，执行结果与候选正确性分别记录。
- 实验根目录：`.agentbenchkit/experiments/sh-agent-c08-c17-c13-20261011/`。
  另有 `-resume1`、`-remaining`、`-c08-final` 三个分别冻结的续跑目录。
- 最终汇总：`final-results.json`；原始中断快照：`interrupted-before-recovery/`；
  离线工具探测：`search-tool-probe.json`；最终完整性核查：`final-integrity.json`。
- 实现验证：`uv run pytest` 252 passed / 16 skipped；Ruff、mypy 通过。
  这是接入工程验证，不是任务通过率。

仅为三个已知任务的探索实验，不是完整 FeatureBench 分数或无偏随机样本。

接入代码提交 `21269a5f494aaac045099d447c6f86999a04cae0` 的远端 CI：
[Ubuntu / Windows 均通过](https://github.com/K529529/AgentBenchKit/actions/runs/38127975722)。


最终完整性检查 PASS：5 次物理执行的原始/归档证据哈希一致，首次中断的原始快照
未变；全部冻结输入和 ABK V0.2 发布运行时代码未变；sh-agent Python 源码未变。
3 次正式 Agent 执行均完成候选冻结、官方判定和容器清理。第一次中断的 sample
仍保留原始 cleanup NOT_RUN，恢复记录另行证明 cleanup_errors=[]，未篡改原状态。
主机只保留实验开始前已有的两个辅助服务，没有遗留本次任务容器。

最终实际模型执行：

| 任务 | Run ID |
| --- | --- |
| C08 | `20261011T093530Z-f72a7adb` |
| C17 | `20261011T092559Z-66037eda` |
| C13 | `20261011T092924Z-5ee80b8f` |
