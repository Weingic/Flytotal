# 2026-04-18 场景测试矩阵 V2

> 2026-07-13 口径说明：下方 2026-04-14 结果是串口命令驱动的台架状态机场景，不是外场真实无人机识别结果。软件场景 PASS 与真实目标/距离矩阵必须分别展示。

## 必测台架场景（6 个）

| 场景 | 输入 | 预期状态 | 预期事件 | 预期视觉 |
| --- | --- | --- | --- | --- |
| 合法目标通过 | TRACK + RID 合法 | `TRACKING/RID_MATCHED/NORMAL` | 无高危事件 | 可 `SEARCHING/LOCKED` |
| 无身份短时穿越 | 短时 TRACK + RID 缺失 | 不直接事件化 | 可无事件 | 可无锁定 |
| 无身份悬停 | 持续 TRACK + RID 缺失 | 升至 `HIGH_RISK` | 打开事件 | 进入抓拍准备 |
| 身份异常目标 | TRACK + RID INVALID | 快速升风险 | 触发事件 | 进入锁定/抓拍 |
| 高风险事件触发 | 持续高危条件 | `HIGH_RISK/EVENT` | `OPEN` | `VISION_LOCKED` 优先 |
| 目标丢失回落 | `TRACK,CLEAR` 或丢失 | 平稳回落 `LOST/IDLE` | 事件关闭 | `VISION_LOST` |

## 台架结果记录口径

1. 每场景记录命令、关键日志、PASS/FAIL 和异常说明。
2. 统一输出到 `captures/latest_acceptance_snapshot.json` 与 `captures/session_logs/*.jsonl`。

## 2026-04-14 台架记录

执行命令：

```powershell
python tools/acceptance_flow_411_单节点闭环验收流程.py --mode full --port COM4 --suite-chain rid_identity_chain_v1,risk_event_vision_chain_v1 --closure-require-vision-lock --no-closure-require-capture-ready
```

结果：台架验收 `5/5 PASS`；`rid_identity_chain_v1` 为 `3/3 PASS`；`risk_event_vision_chain_v1` 为 `6/6 PASS`。该记录证明模拟输入下的状态机和接口，不证明真实目标识别。

证据文件：

1. `captures/latest_411_acceptance_flow_report.json`
2. `captures/latest_single_node_evidence_closure_report.json`
3. `captures/latest_test_session.json`
4. `captures/latest_acceptance_snapshot.json`

## 2026-07-13 真实目标与距离矩阵

当前状态统一为 `PENDING`。只有合法安全场地的原始视频、状态记录和对应结果齐全后，才能修改状态。

### V4b 视觉自动锁定

统一条件：正式 V4b、置信度 `0.45`、自动连续确认、有效画面、每个格子 3 次独立试验。

| 目标 | 10 m 目标 | 30 m 目标 | 50 m 目标 | 必存证据 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| 无人机 | `3/3` 检出并 `YOLO_AUTO` 锁定 | 至少 `2/3` 检出并锁定 | 挑战测试，如实记录 | 原视频、距离、分数、锁定时间、截图 | PENDING |
| 人物 | `0/3` 无人机误锁 | `0/3` 无人机误锁 | `0/3` 无人机误锁 | 原视频、误锁次数、最高分 | PENDING |
| 车辆 | `0/3` 无人机误锁 | `0/3` 无人机误锁 | `0/3` 无人机误锁 | 原视频、误锁次数、最高分 | PENDING |
| 鸟类 | `0/3` 无人机误锁 | `0/3` 无人机误锁 | 自然条件可测时记录 | 原视频、误锁次数、最高分 | PENDING |

50 米无人机若因镜头、目标像素或场地条件不可测，填写 `NOT_TESTABLE` 和原因，不能降低阈值后改成 PASS。

### LD2450 近距二维轨迹

先用人物在约 1.5 到 3 米标定，再逐点增加距离。只在 `track_active=1` 与 `track_confirmed=1` 同时持续成立的位置采集。

| 目标 | 实测有效距离 | 最低调试量 | 正式统计目标 | 当前有效 track | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| 无人机 | 待测 | 5 条 | 至少 20 条 | 0 | PENDING |
| 人物 | 待测 | 5 条 | 至少 20 条 | 0 | PENDING |
| 车辆 | 待测 | 5 条 | 至少 20 条 | 0 | PENDING |
| 鸟类 | 自然条件可测 | 5 条 | 能安全采到多少如实记录 | 0 | PENDING |

`real_tracks.csv` 当前为干净 0 行基线。每段使用唯一 `session-id`，失败和中断也保留记录。

### LD2451 远距运动预警

| 目标 | 距离点 | 每点重复 | 记录字段 | 当前状态 |
| --- | --- | --- | --- | --- |
| 无人机 | 10/30/50 m | 3 | `valid/range/speed/approach/far_motion_trigger` | PENDING |
| 人物 | 10/30/50 m | 3 | 同上，记录误触发和漏触发 | PENDING |
| 车辆 | 10/30/50 m | 3 | 同上，记录距离误差 | PENDING |
| 鸟类 | 自然条件可测 | 不强求 | 同上 | PENDING |

LD2451 通过只证明运动预警，不证明目标类别是无人机。

### 同一事件物联网闭环

| 验收项 | 目标 | 当前状态 |
| --- | --- | --- |
| 新事件号 | 当场创建且未引用历史事件 | PENDING |
| 自动视觉 | `YOLO_AUTO`、drone 类别、有效画面 | PENDING |
| 云端大模型 | `cloud_online=1`、错误为空 | PENDING |
| 下行响应 | 指令已应用或按安全策略明确拒绝，来源事件号一致 | PENDING |
| 抓拍与哈希 | 严格事件绑定、两类 SHA256 可回放 | PENDING |
| 总闸门 | `15/15 PASS` 后生成严格导出 | PENDING |
