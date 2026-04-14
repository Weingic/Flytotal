# 2026-04-09 网页字段映射表 V1

## 目标
把“串口日志 -> bridge JSON -> 网页字段”统一成一张表，避免联调时各看各的。

## 主链关键字段映射

| 串口来源字段 | bridge 统一字段（`latest_node_status.json`） | 网页位置 | 判定说明 |
|---|---|---|---|
| `main_state` | `main_state` | `nodeMainStateValue` | 主状态应和主链一致 |
| `hunter/hunter_state` | `hunter_state` | `nodeHunterValue` | Hunter 子状态 |
| `gimbal/gimbal_state` | `gimbal_state` | `nodeGimbalValue` | 云台状态 |
| `rid/rid_status` | `rid_status` | `nodeRidValue` | RID 状态 |
| `risk/risk_score` | `risk_score` | `paramRiskScoreValue` | 风险分数数值 |
| `risk_level` | `risk_level` | `nodeRiskValue` | 风险等级标签 |
| `track/track_id` | `track_id` | `nodeTrackValue` | 轨迹 ID |
| `active/track_active` | `track_active` | `nodeTrackValue` | 轨迹活跃位 |
| `confirmed/track_confirmed` | `track_confirmed` | `nodeTrackValue` | 轨迹确认位 |
| `x/x_mm` | `x_mm` | `nodePositionValue` | X 坐标 |
| `y/y_mm` | `y_mm` | `nodePositionValue` | Y 坐标 |
| `event_active` | `event_active` | `nodeEventValue` | 事件开关 |
| `event_id/current_event_id` | `event_id` | `nodeEventValue` | 当前事件号 |
| `last_event_id` | `last_event_id` | `nodeLastEventValue` | 最近事件号 |
| `last_reason` | `last_reason` | `nodeLastEventValue` | 最近事件原因 |
| `last_message_type` | `last_message_type` | `nodeMessageValue` | 最近串口消息类型 |

## 4.9 新增：链路一致性字段

| 字段 | 生成位置 | 网页位置 | 说明 |
|---|---|---|---|
| `consistency_status` | `node_a_serial_bridge` | `nodeConsistencyValue` | `OK/WARN/UNKNOWN` |
| `consistency_expected_main_state` | `node_a_serial_bridge` | `nodeConsistencyValue` | 推导主状态，用于对照 |
| `consistency_warnings[]` | `node_a_serial_bridge` | `nodeConsistencyWarnValue` | 映射告警摘要 |
| `consistency_warning_count` | `node_a_serial_bridge` | （可扩展） | 告警数量 |

## 一致性判定规则（当前版本）

- 若 `hunter_state` 推导的主状态与 `main_state` 不一致，则 `WARN`。
- 若 `event_active=1` 但 `event_id=NONE`，则 `WARN`。
- 若 `event_active=0` 但 `event_status=OPEN`，则 `WARN`。
- 若 `track_confirmed=1` 且 `track_active=0`，则 `WARN`。
- 若 `vision_locked=1` 但 `vision_state` 为 `VISION_IDLE/VISION_LOST`，则 `WARN`。
- 若风险分和风险等级明显矛盾（如分数高但等级 `NONE/NORMAL`），则 `WARN`。

## 联调验收口径（4.9）

通过条件：

1. 串口输出字段有值且稳定更新。
2. bridge JSON 字段与串口语义一致。
3. 网页对应卡片刷新一致（不出现“串口 TRACKING、网页 LOST”这类错位）。
4. `consistency_status` 在稳定阶段保持 `OK`（短时过渡 `WARN` 可接受，但需消失）。

辅助核对命令（推荐）：

```powershell
python tools/node_web_consistency_check_NodeA网页一致性核对.py --base-url http://127.0.0.1:8765
```

稳定性观测命令（推荐）：

```powershell
python tools/node_web_consistency_check_NodeA网页一致性核对.py --base-url http://127.0.0.1:8765 --watch-seconds 15 --interval-s 1 --max-fail-samples 0 --quiet-pass
```
