# v5.2 算法公式书

## 1. 融合阶段

距离阶段由可用距离决定：

```text
range = LD2451.range_m if LD2451 fresh else hypot(LD2450.x, LD2450.y) / 1000

FAR  : range > 30m
MID  : 10m <= range <= 30m
NEAR : range < 10m
```

v5.2 默认演示口径：

- FAR：`LD2451` 单源只能 `LOW`，`LD2451 + RID/NodeB` 可到 `MID`。
- MID：`LD2450 / LD2451 / RID / vision` 至少两源且一致，经过 `800ms` 持续窗口后可到 `HIGH`。
- NEAR：必须有视觉确认或 RID 匹配，才允许到 `HIGH`。

## 2. 距离一致性

LD2450 近距雷达距离：

```text
r_near = sqrt(x_mm^2 + y_mm^2)
```

LD2451 远距距离：

```text
r_far = ld2451_range_m * 1000
```

一致性条件：

```text
abs(r_near - r_far) / r_far * 100 <= FusionConfig::RangeAgreementPct
```

当前阈值：`20%`。

## 3. 速度一致性

LD2450 径向速度：

```text
v_radial = (x * vx + y * vy) / sqrt(x^2 + y^2)
```

LD2451 速度：

```text
v_far = abs(ld2451_speed_mps * 1000)
```

一致性条件：

```text
abs(abs(v_radial) - v_far) <= 1500 mm/s
```

方向条件：

```text
approach=true  => v_radial <= +1500 mm/s
approach=false => v_radial >= -1500 mm/s
```

## 4. 视觉投票

视觉有效条件：

```text
vision_locked == true
or vision_state == VISION_LOCKED
or vision_confidence >= 0.5
```

视觉质量输出：

- `CLEAR_LOCKED`：视觉清晰且锁定。
- `DEGRADED_LOCKED`：弱光/雾天但仍有视觉置信度。
- `DEGRADED_VISUAL`：弱光/雾天且没有可靠视觉锁定。
- `VISION_LOST`：视觉链路丢失。

## 5. 多旋翼筛选

多旋翼评分不是“识别无人机型号”，而是过滤明显不像无人机的目标。

四个特征：

1. 速度区间：`2000 <= speed_mm_s <= 25000`。
2. 持续时长：连续航迹 `>= 2000ms`。
3. 悬停稳定性：`speed_variance_mm_s <= 900` 时保留悬停可能性。
4. 航向变化率：`heading_rate_deg_s > 75` 时扣分。

启用 `MultirotorConfig::Enabled=true` 后，非多旋翼目标不得直接进入 `EVENT`，最多停在 `HIGH_RISK`。

## 6. 云台预测

基础速度：

```text
vx = (x_now - x_last) / dt
vy = (y_now - y_last) / dt
```

加速度限幅：

```text
ax = clamp((vx - vx_last) / dt, -5000, 5000)
ay = clamp((vy - vy_last) / dt, -5000, 5000)
```

一阶低通：

```text
ax_filt = 0.7 * ax_filt + 0.3 * ax
ay_filt = 0.7 * ay_filt + 0.3 * ay
```

二阶外推：

```text
x_pred = x + vx * lead + 0.5 * ax_filt * lead^2
y_pred = y + vy * lead + 0.5 * ay_filt * lead^2
```

当前 `lead=0.18s`，用于覆盖云台机械响应、串口和主循环延迟。

v5.2 P0.2 增加换目标复位：

```text
if new_track_id != last_track_id:
    last_x = x_now
    last_y = y_now
    last_vx = 0
    last_vy = 0
    ax_filt = 0
    ay_filt = 0
```

这样新目标不会继承前一个目标的速度和加速度，避免云台在目标切换瞬间抽搐。

## 7. LD2451 串口完整性策略

LD2451 官方帧在当前接入协议中使用：

```text
Header  = F4 F3 F2 F1
Length  = uint16 little-endian
Payload = target_count + alarm + target[5] * N
Tail    = F8 F7 F6 F5
```

当前不伪造 CRC。原因是官方上报帧没有可用于校验的 CRC 字段，如果自己定义 CRC，只能用于文本仿真或自定义上位机，不能验证真实 LD2451 二进制帧。

实际采用四层防护：

```text
1. header/tail 必须匹配
2. payload length 必须等于 2 + target_count * 5
3. 字段范围必须合法：target_count、alarm、angle、range、direction、speed
4. 真实二进制帧需要连续 2 帧稳定才写入主链
```

连续帧稳定条件：

```text
abs(range_now - range_pending) <= 1m
abs(speed_now - speed_pending) <= 2km/h
abs(angle_now - angle_pending) <= 2deg
approach_now == approach_pending
```

验收命令：

```text
LD2451,SELFTEST
```

该命令会跑正常帧、无目标帧、错误帧尾、长度错误、字段非法 5 个样例。

## 8. 异常值守卫

雷达测量进入 TrackManager 前必须满足：

```text
isfinite(x_mm) == true
isfinite(y_mm) == true
abs(x_mm) <= RadarConfig::MaxCoordinateAbsMm
abs(y_mm) <= RadarConfig::MaxCoordinateAbsMm
```

当前 `MaxCoordinateAbsMm=100000`，也就是 100m 量级边界。非法值只输出节流警告，不进入云台和风险状态。

## 9. ConfirmFrames=5 的答辩口径

`TrackConfig::ConfirmFrames=5` 保持不改。理由：

- LD2450 是近距航迹源，近距直接影响云台和事件状态，宁愿慢一点也要降低误报。
- 100m 远距预警不依赖 LD2450 的 5 帧确认，而由 LD2451 的 FAR 触发链承担。
- 如果把 5 帧改成 3 帧，近距响应更快，但行人/摆动物体/串口毛刺更容易进入确认航迹。
- 答辩口径：近距确认重稳定，远距预警重触发，两个链路职责不同。

## 10. Watchdog 和串口缓冲

Watchdog 当前 `TimeoutSeconds=12`：

```text
RadarTask / NodeBTask / Ld2451Task / TrackingTask / CloudTask
均注册 esp_task_wdt_add(nullptr)
并在主循环喂狗
```

串口逐字符输入使用固定行缓冲：

```text
char line[256]
length++
newline => 构造一次 String 并进入原解析链
overflow => 丢弃当前行并等待下一次换行
```

这样保留原有命令解析逻辑，同时避免每个字符都触发 `String += ch` 的堆重分配。

## 给小白的解释

融合算法不是“哪个传感器说了算”，而是“多个证据有没有互相支持”。远处先预警，近处再确认；视觉好就加分，视觉差也不会让系统完全失明。
