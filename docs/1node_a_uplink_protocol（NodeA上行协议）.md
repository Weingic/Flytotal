# Node A 串口上行协议说明

本文档用于固定当前 `Node A` 的串口输出格式与主机命令格式，内容仅覆盖当前代码中已经实现的部分。

## 适用范围

- 当前主控：ESP32-S3
- 当前节点编号：`A1`
- 当前节点角色：`EDGE`
- 当前输出通道：USB 串口监视器
- 当前波特率：`115200`

## 当前支持的主机命令

以下命令通过 USB 串口发送给 ESP32，每条命令单独一行，按回车结束。

### HELP

功能：
- 打印当前支持的命令列表。

示例：

```text
HELP
```

### STATUS

功能：
- 输出当前系统状态快照。

示例：

```text
STATUS
```

返回示例：

```text
STATUS,node=A1,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,track=0,active=0,confirmed=0,x=0.0,y=0.0,test_mode=0,servo_enabled=1,manual_pan=90.0,manual_tilt=90.0,safe_mode=0,diag_running=0,debug=1,uplink=1
```

### SELFTEST

功能：
- 输出当前单板自检摘要。
- 用于在不接雷达、不接云台时快速确认主程序关键状态。

示例：

```text
SELFTEST
```

返回示例：

```text
SELFTEST,BEGIN
SELFTEST,node=A1,role=EDGE
SELFTEST,monitor_baud=115200,radar_baud=256000
SELFTEST,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0
SELFTEST,track=0,active=0,confirmed=0,x=0.0,y=0.0,vx=0.0,vy=0.0
SELFTEST,sim_enabled=0,sim_active=0,sim_x=0.0,sim_y=0.0,sim_hold_ms=1500
SELFTEST,test_mode=0,servo_enabled=1,servo_attached=1,manual_pan=90.0,manual_tilt=90.0,safe_mode=0,diag_running=0,debug=1,uplink=1
SELFTEST,predictor_kp=0.450,predictor_kd=0.050
SELFTEST,heartbeat_ms=1000,event_report_ms=250
SELFTEST,idle_ready=1
SELFTEST,END
```

### DEBUG,ON

功能：
- 打开本地调试输出。
- 会继续输出 `GIMBAL / DATA / STATE`。

### DEBUG,OFF

功能：
- 关闭本地调试输出。
- 关闭后不再输出 `GIMBAL / DATA / STATE`，但 `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` 仍然保留。

说明：
- 当串口刷屏太快、影响命令输入时，优先使用 `DEBUG,OFF`。

### UPLINK,ON

功能：
- 打开 `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` 输出。

### UPLINK,OFF

功能：
- 关闭 `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` 输出。

说明：
- 当你只想调试舵机命令、不想看任何上行刷屏时，使用 `UPLINK,OFF`。
- `RESET` 后会恢复为 `UPLINK,ON`。

### SAFE,ON

功能：
- 打开保守安全角度限制。
- 打开后，手动测试与诊断使用更小的安全角度范围。

### SAFE,OFF

功能：
- 关闭保守安全角度限制。
- 关闭后，恢复当前默认角度限制。

### DIAG,SERVO

功能：
- 启动舵机引导诊断流程。
- 程序会自动打开 `SAFE,ON`、`SERVO,ON`、`TESTMODE,ON`。
- 然后按“中心位、小左、小右、小上、小下、回中心”的顺序自动测试。

说明：
- 该流程不能读取舵机真实反馈，但会把每一步的目标角度和观察提示直接打印出来。
- 如果任何一步出现剧烈抖动，应立即输入 `DIAG,STOP` 或 `SERVO,OFF`。

### DIAG,STOP

功能：
- 立即停止当前舵机引导诊断流程。
- 不会自动恢复自动主链；如需恢复，继续使用 `TESTMODE,OFF`。

### TESTMODE,ON

功能：
- 打开云台手动测试模式。
- 打开后，舵机输出由串口手动命令接管，不再跟随自动跟踪输出。

示例：

```text
TESTMODE,ON
```

### TESTMODE,OFF

功能：
- 关闭云台手动测试模式。
- 关闭后，系统恢复当前自动主链控制。

### SERVO,ON

功能：
- 使能舵机 PWM 输出。
- 适合在确认供电和机械状态后再打开舵机。

### SERVO,OFF

功能：
- 关闭舵机 PWM 输出。
- 适合在接线、断电前或发现乱动时快速停输出。

### CENTER

功能：
- 将手动测试目标角度置回中心位。
- 当前中心位来自 `CenterPanDeg` 与 `CenterTiltDeg`。

### PAN,value

功能：
- 设置手动测试模式下的水平目标角度。
- 角度会被限制在当前安全范围内。

示例：

```text
PAN,60
```

### TILT,value

功能：
- 设置手动测试模式下的俯仰目标角度。
- 角度会被限制在当前安全范围内。

示例：

```text
TILT,100
```

### TRACK,x,y

功能：
- 注入模拟轨迹坐标，替代真实雷达输入。
- 适合在无雷达条件下继续推进 `TrackManager -> HunterAction -> GimbalController -> UPLINK` 主链。

示例：

```text
TRACK,320,1800
```

返回示例：

```text
Simulation track updated: x=320.0,y=1800.0
```

说明：
- 一次注入后，系统会在短时间内持续复用该点，直到超时或清除。
- 这样单次命令也足以让轨迹进入确认流程。

### TRACK,CLEAR

功能：
- 清除当前模拟轨迹。

示例：

```text
TRACK,CLEAR
```

返回示例：

```text
Simulation track cleared.
```

### RID,OK

功能：
- 将当前 RID 状态设为 `MATCHED`。

### RID,MISSING

功能：
- 将当前 RID 状态设为 `MISSING`。

### RID,SUSPICIOUS

功能：
- 将当前 RID 状态设为 `SUSPICIOUS`。

### KP,value

功能：
- 动态修改预测器运行时 `Kp` 参数。

示例：

```text
KP,0.60
```

### KD,value

功能：
- 动态修改预测器运行时 `Kd` 参数。

示例：

```text
KD,0.10
```

### RESET

功能：
- 将 `rid_status` 恢复为 `UNKNOWN`
- 清除模拟轨迹
- 将 `Kp` 和 `Kd` 恢复为默认值

示例：

```text
RESET
```

## 串口调试输出

### GIMBAL

功能：
- 输出云台当前状态和目标轨迹摘要。

示例：

```text
GIMBAL,SCANNING,test_mode=0,servo_enabled=1,track_active=0,confirmed=0,x=0.0,y=0.0,vx=0.0,vy=0.0
```

说明：
- 当前本地调试输出已做限频，不再按每个控制循环完整刷出。
- 当前 `GIMBAL`、`STATUS`、`SELFTEST` 中还会带出 `safe_mode` 和 `diag_running`，方便确认当前是否处于保护/诊断状态。

### DATA

功能：
- 输出给上位机画图使用的简化数据。

示例：

```text
DATA,1500.0,92.5
```

说明：
- 第 1 列：目标 `x_mm`
- 第 2 列：当前 `pan_angle`

### STATE

功能：
- 输出 Hunter 当前状态与风险分数。

示例：

```text
STATE,SUSPICIOUS,57.0
```

## UPLINK,HB

功能：
- 心跳帧
- 周期性输出当前节点整体状态

输出周期：
- `CloudConfig::HeartbeatMs`

示例：

```text
UPLINK,HB,node=A1,role=EDGE,ts=12345,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,alert=0,capture=0,guardian=0
```

## SUMMARY 鎵╁睍锛?2026-04-01

### SUMMARY

鍔熻兘锛?
- 杈撳嚭褰撳墠寮€鏈轰互鏉ョ殑鑱旇皟鎽樿缁熻銆?
- 閫傚悎鍦ㄧ湡瀹為浄杈炬垨妯℃嫙杞ㄨ抗璺戜竴杞悗锛屽揩閫熺湅涓婚摼鏄惁鐪熸璧拌繃銆?

绀轰緥锛?
```text
SUMMARY
```

杩斿洖绀轰緥锛?
```text
SUMMARY,node=A1,uptime_ms=24567,track_active=2,track_confirmed=1,track_lost=1,gimbal_tracking=1,gimbal_lost=1,hunter_changes=3,max_risk=57.0,last_track=4,last_x=320.0,last_y=1800.0,last_event_id=A1-0000023456-0001
```

瀛楁鍚箟锛?
- `track_active`锛氭湰娆″紑鏈轰互鏉ヨ繘鍏?`active=1` 鐨勬鏁般€?
- `track_confirmed`锛氭湰娆″紑鏈轰互鏉ヨ繘鍏?`confirmed=1` 鐨勬鏁般€?
- `track_lost`锛氭湰娆″紑鏈轰互鏉ョ洰鏍囦涪澶辩殑娆℃暟銆?
- `gimbal_tracking` / `gimbal_lost`锛氫簯鍙板垏鍏?`TRACKING / LOST` 鐨勬鏁般€?
- `hunter_changes`锛歕unter 鐘舵€佸垏鎹㈡鏁般€?
- `max_risk`锛氭湰娆″紑鏈轰互鏉ョ殑鏈€楂橀闄╁垎銆?
- `last_track` / `last_x` / `last_y`锛氭渶杩戜竴娆℃湁鏁堢洰鏍囩殑 ID 鍜屽潗鏍囥€?
- `last_event_id`锛氭渶杩戜竴娆¤仈鍔ㄤ簨浠剁殑浜嬩欢缂栧彿锛屽鏋滆繕娌℃湁鍒欎负 `NONE`銆?

### SUMMARY,RESET

鍔熻兘锛?
- 娓呯┖褰撳墠 `SUMMARY` 缁熻锛屼粠姝ゅ埢閲嶆柊寮€濮嬭鏁般€?

绀轰緥锛?
```text
SUMMARY,RESET
```

## ZONE 扩展：2026-04-01

当前节点已新增固定字段 `zone`，用于表示节点所属区域/扇区。

当前默认值：

```text
ZONE_NORTH
```

当前输出位置：

- `STATUS`
- `SELFTEST`
- `SUMMARY`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`

示例：

```text
UPLINK,HB,node=A1,zone=ZONE_NORTH,role=EDGE,ts=12345,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,alert=0,capture=0,guardian=0
```

字段说明：

- `node`：节点编号
- `role`：节点角色
- `ts`：系统运行毫秒时间戳
- `hunter`：Hunter 状态
- `gimbal`：云台状态
- `rid`：RID 状态
- `risk`：当前风险分数
- `alert`：是否触发本地告警
- `capture`：是否触发抓拍动作
- `guardian`：是否触发合作终端保障链路

## UPLINK,TRACK

功能：
- 轨迹帧
- 当存在活跃目标时，周期性输出轨迹信息

输出条件：
- `snapshot.radar_track.is_active == true`

输出周期：
- `CloudConfig::EventReportMs`

示例：

```text
UPLINK,TRACK,node=A1,ts=12600,track=3,active=1,confirmed=1,x=320.0,y=1800.0,vx=40.0,vy=-10.0,seen=12,lost=0
```

字段说明：

- `track`：轨迹编号
- `active`：轨迹当前是否活跃
- `confirmed`：轨迹是否已确认
- `x / y`：当前坐标
- `vx / vy`：速度估计
- `seen`：连续观测计数
- `lost`：丢失计数

## UPLINK,EVENT

功能：
- 事件帧
- 当关键状态发生变化时立即输出

当前 `reason` 类型：

- `TRACK_CHANGED`：换目标了！
- `TRACK_ACTIVE`：发现新目标
- `TRACK_LOST`：目标跟丢了/已消失！
- `HUNTER_STATE`：猎手：威胁等级升级/降级！
- `RID_STATE`：身份：查明正身！

示例：

```text
UPLINK,EVENT,node=A1,ts=12700,reason=TRACK_ACTIVE,track=3,hunter=SUSPICIOUS,gimbal=TRACKING,rid=MISSING,risk=63.0,alert=1,capture=1,guardian=0,x=320.0,y=1800.0
```

## 当前状态枚举

### Hunter 状态

- `IDLE`:待机 / 闲置
- `TRACKING`:追踪中 / 保持警惕
- `RID_MATCHED`:友军锁定 / 警报解除
- `SUSPICIOUS`:可疑目标 / 黄色警报
- `HIGH_RISK`:高危 / 红色防空警报
- `EVENT_LOCKED`：事件锁定 / 武装打击开始！

### 云台状态

- `SCANNING`
- `ACQUIRING`
- `TRACKING`
- `LOST`

### RID 状态

- `UNKNOWN`
- `MATCHED`
- `MISSING`：缺失 / 黑飞
- `SUSPICIOUS`：可疑 / 套牌

## 说明

- 当前协议是串口优先的调试与联调用格式。
- 当前已经支持模拟轨迹注入，因此在无雷达条件下也能看到 `UPLINK,TRACK` 和相关事件输出。
- 后续如果进入云端或双节点联调，应优先基于本文档继续扩展，而不是另起一套命名。
