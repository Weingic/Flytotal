# 2026-03-30 ESP32 单板测试清单

目标：仅通过 USB 给 Node A 主程序上电，在不连接雷达和云台硬件的情况下完成基础验证，并通过模拟轨迹注入继续推进主链测试。

## 接线

- 只通过 USB 连接 ESP32-S3 开发板。
- 今天这轮测试不要连接雷达、舵机、蜂鸣器或其他执行器。

## 烧录与串口监视

- 构建：`pio run`
- 烧录：`pio run -t upload`
- 打开串口监视器：`pio device monitor -b 115200`

可选的自动化冒烟测试：

- `python tools/esp32_single_board_test_单板测试.py --port COM4`

如果 `pio` 没有加入 PATH，请使用：

- `C:\Users\WZwai\.platformio\penv\Scripts\pio.exe run`
- `C:\Users\WZwai\.platformio\penv\Scripts\pio.exe device monitor -b 115200`

## 预期启动日志

上电后，串口监视器应看到：

- `Node A control chain starting`
- `Single-board test mode is supported over USB serial.`
- `CloudTask publishes UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT frames.`
- `Host commands:` 帮助信息块

空闲状态下，正常输出应包含：

- `GIMBAL,SCANNING,track_active=0,confirmed=0,...`
- `UPLINK,HB,node=A1,... hunter=IDLE,gimbal=SCANNING,...`

## 今日测试命令

每条命令单独发送一行，回车结束。

### 基础命令

`HELP`
- 应打印当前支持的命令列表。

`STATUS`
- 应打印一条简洁的当前状态快照。

`SELFTEST`
- 应打印一组单板自检摘要。
- 在没接雷达时，通常会看到 `idle_ready=1`。

### RID 与参数命令

`RID,OK`
- 应将 RID 状态更新为 `MATCHED`。

`RID,MISSING`
- 应将 RID 状态更新为 `MISSING`。

`RID,SUSPICIOUS`
- 应将 RID 状态更新为 `SUSPICIOUS`。

`KP,0.60`
- 应打印更新后的运行时 `Kp`。

`KD,0.10`
- 应打印更新后的运行时 `Kd`。

`RESET`
- 应将 RID 状态恢复为 `UNKNOWN`。
- 应将模拟轨迹清空。
- 应将 `Kp` 和 `Kd` 恢复为默认值。

### 主线验证命令

`TRACK,320,1800`
- 应注入一个模拟目标。
- 一段时间后应看到：
  - `track_active=1`
  - `confirmed=1`
  - `UPLINK,TRACK`
  - 云台状态从 `SCANNING` 进入 `ACQUIRING`，再进入 `TRACKING`

`TRACK,CLEAR`
- 应清除当前模拟目标。
- 稍后轨迹应超时消失，并重新回到无目标状态。

## 今日主线验收标准

### 基础通过

- 开发板能通过 USB 正常启动。
- 串口测试过程中没有出现崩溃或反复重启。
- `HELP`、`STATUS`、`SELFTEST` 能正常工作。
- `RID`、`KP`、`KD`、`RESET` 命令都能得到正确反馈。
- `UPLINK,HB` 能保持每秒持续输出。

### 主线通过

- `TRACK,x,y` 注入后，系统能形成活跃轨迹。
- 轨迹能进入 `confirmed=1`。
- 串口能看到 `UPLINK,TRACK`。
- 云台状态机能进入 `TRACKING`。
- `TRACK,CLEAR` 后系统能回到空闲态。

## 今日记录项

请记录：

- 今天使用的 COM 口
- 是否启动成功
- 是否出现异常重启
- 一条实际空闲心跳示例
- 一条实际状态快照示例
- 一条实际 `SELFTEST` 示例
- 一条实际 `UPLINK,TRACK` 示例
- `TRACK` 注入后是否成功进入 `TRACKING`
- 是否有命令表现不符合预期

