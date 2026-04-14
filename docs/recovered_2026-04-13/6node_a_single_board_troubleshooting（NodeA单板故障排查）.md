# Node A 单板测试异常排查与结果判�?
本文档用于配合今天的单板测试目标使用�? 
适用场景�?
- 只连�?ESP32-S3 �?USB
- 不连接雷�?- 不连接云台舵�?- 重点验证主程序启动��串口命令��状态输出��心跳输�?
相关文档�?
- [2026-03-30_esp32_single_board_checklist��ESP32�������嵥��.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-03-30_esp32_single_board_checklist��ESP32�������嵥��.md)
- [2026-03-30_esp32_single_board_record��ESP32�����¼��.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-03-30_esp32_single_board_record��ESP32�����¼��.md)
- [1node_a_uplink_protocol��NodeA����Э�飩.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/1node_a_uplink_protocol��NodeA����Э�飩.md)

## 丢�、今天测试��过的最低标�?
如果满足以下 5 条，就可以认为今天的单板测试是��过的：

1. ESP32 能正常上电并启动程序
2. 串口能看到启动提�?3. `HELP` 命令有响�?4. `STATUS` 命令有响�?5. `UPLINK,HB` 能持续输�?
说明�?- 今天不要求看到真实轨�?- 今天不要求进入真�?`TRACKING`
- 今天不要求舵机动�?
## 二��今天预期看到的正常现象

### 1. 启动�?
正常应看到类似信息：

```text
Node A control chain starting
Single-board test mode is supported over USB serial.
CloudTask publishes UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT frames.
Host commands:
```

### 2. 空闲运行�?
正常应看到类似信息：

```text
GIMBAL,SCANNING,track_active=0,confirmed=0,x=0.0,y=0.0,vx=0.0,vy=0.0
UPLINK,HB,node=A1,role=EDGE,ts=...,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,alert=0,capture=0,guardian=0
```

说明�?- 没接雷达时，`track_active=0` 是正常现�?- 没接雷达时，`confirmed=0` 是正常现�?- 没接雷达时，没有 `UPLINK,TRACK` 也正�?
## 三��最常见的几类问�?
### 问题 1：烧录成功了，但串口没有任何输出

优先棢�查：

1. 串口波特率是否为 `115200`
2. 是否打开了正确的 COM �?3. USB 线是否支持数据传输，而不只是供电
4. 板子是否在反复重�?5. 是否等待了至�?2 秒以�?
原因说明�?- 当前程序�?`setup()` 里有 `StartupDelayMs = 2000`
- 扢�以上电后不会立刻看到日志

### 问题 2：串口有输出，但都是乱码

优先棢�查：

1. 串口监视器波特率是否设成 `115200`
2. 是否用了错误的串口工具配�?
原因说明�?- 当前 `MonitorBaudRate` 固定�?`115200`

### 问题 3：能看到日志，但 `HELP` 没反�?
优先棢�查：

1. 串口工具是否发��了换行
2. 是否同时弢�启了另一个程序占用串�?3. 输入是否真的�?`HELP`
4. 是否按回车发�?
原因说明�?- 当前命令解析器按“遇到换行或回车”才处理命令

### 问题 4：`STATUS` 没反�?
优先棢�查：

1. `HELP` 是否正常
2. 是否有回车结�?3. 串口发��格式是否为纯文�?
如果 `HELP` 正常�?`STATUS` 不正常：
- 记录现象
- 把对应串口输出保存下�?
### 问题 5：`RID,OK` 发了，但没看到状态变�?
优先棢�查：

1. 是否看到 `RID simulation updated: OK`
2. 后续心跳�?`rid=` 是否变成 `MATCHED`
3. `STATUS` 输出里的 `rid=` 是否变化

说明�?- 在没有活跃轨迹时，`hunter_state` 不一定会立刻表现出明显变�?- �?`rid_status` 本身应该变化

### 问题 6：只看到 `UPLINK,HB`，看不到 `UPLINK,TRACK`

这��常是正常的�?
原因�?- `UPLINK,TRACK` 只有�?`snapshot.radar_track.is_active == true` 时才会输�?- 今天没接雷达，所以��常不会有活跃轨�?
### 问题 7：只看到 `SCANNING`，看不到 `TRACKING`

这��常也是正常的��?
原因�?- 云台状��机要等 `track.is_confirmed == true` 才可能进�?`ACQUIRING` �?`TRACKING`
- 今天没接雷达，所以长期停留在 `SCANNING` 是正常结�?
### 问题 8：程序不断重�?
优先棢�查：

1. USB 供电是否稳定
2. 是否接了其他可能拉低电压的外�?3. 串口日志里是否有重复启动信息
4. 是否存在错误的自动上�?自动打开串口行为

今天测试建议�?- 只接 USB
- 不接舵机
- 不接雷达

## 四��今天的结果如何判定

### 情况 A：完全��过

满足条件�?
- 能稳定启�?- `HELP` 正常
- `STATUS` 正常
- `RID / KP / KD / RESET` 都有反馈
- `UPLINK,HB` 稳定输出

说明�?- 可以认为今天的��ESP32 单板主程序验证��完�?
### 情况 B：部分��过

满足条件�?
- 能启�?- 有心�?- 但个别命令异�?
说明�?- 今天主程序基本可运行
- 霢�要把异常命令单独记录，明天继续修

### 情况 C：未通过

满足条件�?
- 无法启动
- 或启动后持续重启
- 或串口完全无输出

说明�?- 今天应优先解决基硢�启动问题
- 暂时不要进入下一阶段

## 五��今天如果��过，下丢�步该做什�?
如果今天单板测试通过，下丢�步建议优先做�?
1. 把实际串口输出填进测试记录模�?2. 固定丢�条启动日志示�?3. 固定丢�条空闲心跳示�?4. 固定丢��?`STATUS` 示例
5. 准备下一阶段的模拟输入方�?
## 六��今天如果没通过，至少要留下仢��?
即使今天没完全��过，也建议至少记录�?
- 使用�?COM �?- 上电后是否有任何输出
- 输出内容截图或复制文�?- 哪条命令无响�?- 是否出现反复重启

这样明天继续推进时，不会从零弢�始回忆��?
## 七��结�?
今天的单板测试，本质上是在验证：

- 程序是否能正常启�?- 命令链是否可�?- 状��查询是否可�?- 上行心跳是否可用

只要这四条成立，今天就已经完成了丢�个很重要的阶段目标��? 
接下来的工作，才值得继续徢�模拟输入、硬件联调和云端对接推进�?
