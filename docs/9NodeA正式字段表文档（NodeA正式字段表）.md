# Node A 上行字段表

日期：`2026-04-01`

本文档用于将当前 `Node A` 已实现的串口上行帧整理为正式字段表，便于后续云端、A2 节点、上位机或材料编写时直接复用。

说明：
- 本文档只描述当前代码已经实现的字段。
- 本文档不扩展未来字段，不假设未实现功能。
- 当前上行帧均由 [main.cpp](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/src/main.cpp) 中的 `CloudTask` 输出。

## 一、帧类型总览

当前 `Node A` 已实现 3 类上行帧：

1. `UPLINK,HB`
2. `UPLINK,TRACK`
3. `UPLINK,EVENT`

## 二、UPLINK,HB 字段表

帧含义：
- 心跳帧
- 周期性输出当前节点整体状态

触发条件：
- 每经过 `CloudConfig::HeartbeatMs`

示例：

```text
UPLINK,HB,node=A1,zone=ZONE_NORTH,role=EDGE,ts=40229,hunter=IDLE,gimbal=LOST,rid=UNKNOWN,risk=0.0,alert=0,capture=0,guardian=0
```

字段表：

| 字段名 | 类型 | 含义 | 示例 |
| --- | --- | --- | --- |
| `node` | 字符串 | 节点编号 | `A1` |
| `zone` | 字符串 | 节点所属区域/扇区 | `ZONE_NORTH` |
| `role` | 字符串 | 节点角色 | `EDGE` |
| `ts` | 整数 | 系统运行毫秒时间戳 | `40229` |
| `hunter` | 枚举字符串 | Hunter 当前状态 | `IDLE` |
| `gimbal` | 枚举字符串 | 云台当前状态 | `LOST` |
| `rid` | 枚举字符串 | 当前 RID 状态 | `UNKNOWN` |
| `risk` | 浮点数 | 当前风险分数 | `0.0` |
| `alert` | 整数布尔值 | 是否触发本地告警 | `0` |
| `capture` | 整数布尔值 | 是否触发抓拍动作 | `0` |
| `guardian` | 整数布尔值 | 是否触发合作终端保障链路 | `0` |

## 三、UPLINK,TRACK 字段表

帧含义：
- 轨迹帧
- 当存在活跃目标时，周期性输出轨迹信息

触发条件：
- `snapshot.radar_track.is_active == true`
- 且达到 `CloudConfig::EventReportMs` 周期

示例：

```text
UPLINK,TRACK,node=A1,zone=ZONE_NORTH,ts=37727,event_id=A1-0000037727-0001,source_node=A1,track=3,active=1,confirmed=1,x=0.0,y=1800.0,vx=0.0,vy=0.0,seen=327,lost=0
```

字段表：

| 字段名 | 类型 | 含义 | 示例 |
| --- | --- | --- | --- |
| `node` | 字符串 | 节点编号 | `A1` |
| `zone` | 字符串 | 节点所属区域/扇区；当前阶段固定配置输出 | `ZONE_NORTH` |
| `ts` | 整数 | 系统运行毫秒时间戳 | `37727` |
| `event_id` | 字符串，可选 | 当前关联事件编号；仅在已形成事件上下文时输出 | `A1-0000037727-0001` |
| `source_node` | 字符串，可选 | 当前事件最初来源节点；当前阶段固定为本节点 | `A1` |
| `track` | 整数 | 当前轨迹编号 | `3` |
| `active` | 整数布尔值 | 轨迹是否活跃 | `1` |
| `confirmed` | 整数布尔值 | 轨迹是否已确认 | `1` |
| `x` | 浮点数 | 当前横向坐标，单位 mm | `0.0` |
| `y` | 浮点数 | 当前纵向/距离坐标，单位 mm | `1800.0` |
| `vx` | 浮点数 | 横向速度估计，单位 mm/s | `0.0` |
| `vy` | 浮点数 | 纵向速度估计，单位 mm/s | `0.0` |
| `seen` | 整数 | 当前轨迹累计观测计数 | `327` |
| `lost` | 整数 | 当前轨迹丢失计数 | `0` |

## 四、UPLINK,EVENT 字段表

帧含义：
- 事件帧
- 当关键状态变化时立即输出

当前已实现的 `reason`：

- `TRACK_CHANGED`
- `TRACK_ACTIVE`
- `TRACK_LOST`
- `HUNTER_STATE`
- `RID_STATE`
- `HANDOVER`

示例：

```text
UPLINK,EVENT,node=A1,zone=ZONE_NORTH,ts=38879,event_id=A1-0000037727-0001,source_node=A1,reason=HUNTER_STATE,event_level=WARN,event_status=OPEN,track=3,hunter=SUSPICIOUS,gimbal=TRACKING,rid=MISSING,risk=55.0,alert=1,capture=0,guardian=0,x=0.0,y=2600.0
```

字段表：

| 字段名 | 类型 | 含义 | 示例 |
| --- | --- | --- | --- |
| `node` | 字符串 | 节点编号 | `A1` |
| `zone` | 字符串 | 节点所属区域/扇区；当前阶段固定配置输出 | `ZONE_NORTH` |
| `ts` | 整数 | 系统运行毫秒时间戳 | `38879` |
| `event_id` | 字符串，可选 | 当前关联事件编号；在事件已建立后输出 | `A1-0000037727-0001` |
| `source_node` | 字符串，可选 | 当前事件最初来源节点；当前阶段固定为本节点 | `A1` |
| `reason` | 枚举字符串 | 事件触发原因 | `HUNTER_STATE` |
| `event_level` | 枚举字符串 | 事件等级；当前实现为 `INFO / WARN / CRITICAL` | `WARN` |
| `event_status` | 枚举字符串 | 当前处置状态；当前实现为 `OPEN / CLOSED` | `OPEN` |
| `handover_from` | 字符串，可选 | 接力来源节点；仅在 `reason=HANDOVER` 时输出 | `A1` |
| `handover_to` | 字符串，可选 | 接力目标节点；仅在 `reason=HANDOVER` 时输出 | `A2` |
| `track` | 整数 | 当前轨迹编号 | `3` |
| `hunter` | 枚举字符串 | Hunter 当前状态 | `IDLE` |
| `gimbal` | 枚举字符串 | 云台当前状态 | `LOST` |
| `rid` | 枚举字符串 | 当前 RID 状态 | `MISSING` |
| `risk` | 浮点数 | 当前风险分数 | `0.0` |
| `alert` | 整数布尔值 | 是否触发本地告警 | `0` |
| `capture` | 整数布尔值 | 是否触发抓拍动作 | `0` |
| `guardian` | 整数布尔值 | 是否触发合作终端保障链路 | `0` |
| `x` | 浮点数 | 事件发生时横向坐标，单位 mm | `0.0` |
| `y` | 浮点数 | 事件发生时纵向坐标，单位 mm | `2600.0` |

## 五、当前枚举值说明

### 1. Hunter 状态

| 枚举值 | 含义 |
| --- | --- |
| `IDLE` | 当前无活跃目标 |
| `TRACKING` | 当前处于普通跟踪阶段 |
| `RID_MATCHED` | 当前目标已匹配合法 RID |
| `SUSPICIOUS` | 当前目标为可疑目标 |
| `HIGH_RISK` | 当前目标为高风险目标 |
| `EVENT_LOCKED` | 当前目标进入事件锁定态 |

### 2. 云台状态

| 枚举值 | 含义 |
| --- | --- |
| `SCANNING` | 扫描待机 |
| `ACQUIRING` | 捕获确认 |
| `TRACKING` | 正式跟踪 |
| `LOST` | 目标暂时丢失 |

### 3. RID 状态

| 枚举值 | 含义 |
| --- | --- |
| `UNKNOWN` | 当前未知 |
| `MATCHED` | 当前已匹配合法 RID |
| `MISSING` | 当前缺失 RID |
| `SUSPICIOUS` | 当前 RID 可疑 |

## 六、对接注意事项

1. 当前上行格式是“逗号分隔 + `key=value`”的文本格式，不是 JSON。
2. `UPLINK,TRACK` 只有在活跃轨迹存在时才会输出。
3. `event_id` 与 `source_node` 当前只在已形成事件上下文后附带输出；当前事件上下文的建立条件是“轨迹活跃且已确认”。
4. `UPLINK,EVENT` 当前会额外附带 `event_level` 与 `event_status`，用于给云端或上位机提供更直接的事件语义。
5. 当前 `event_level` 映射为：普通轨迹类事件 `INFO`，`SUSPICIOUS` 为 `WARN`，`HIGH_RISK / EVENT_LOCKED` 为 `CRITICAL`。
6. 当前 `event_status` 映射为：活跃事件为 `OPEN`，目标丢失或轨迹失活后为 `CLOSED`。
7. 当 `reason=HANDOVER` 时，会额外输出 `handover_from` 与 `handover_to`，用于给后续多节点协同或云端接力流程提供统一字段。
8. `UPLINK,EVENT` 是状态变化触发，不保证固定周期；当目标丢失时，`TRACK_LOST` 仍会带上刚刚结束的 `event_id`，便于云端串联同一事件。
9. 当前字段命名已经可以作为后续 MQTT 或云端 JSON 字段的命名参考。

## 七、当前阶段结论

到这一步，`Node A` 当前已实现的上行协议已经具备：

- 帧分类
- 字段定义
- 类型约束
- 示例参考
- 触发条件说明

这意味着后续进入双节点联调或云端对接时，已经有一份可直接交付的字段表，不需要再从 `main.cpp` 中逐行整理。
