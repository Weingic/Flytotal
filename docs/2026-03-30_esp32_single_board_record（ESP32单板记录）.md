# 2026-03-30 ESP32 单板测试记录

## 基本信息

- 测试日期：
- 测试地点：
- 测试人员：
- 开发板型号：
- 使用串口：
- 固件版本或说明：

## 接线情况

- 是否仅接 USB：是 / 否 
- 是否连接雷达：是 / 否
- 是否连接云台舵机：是 / 否
- 是否连接其他外设：是 / 否
- 备注：

## 启动结果

- 是否成功启动：是 / 否
- 启动后是否持续输出日志：是 / 否
- 是否出现异常重启：是 / 否
- 启动现象说明：

## 基础命令测试结果

### HELP

- 是否正常：是 / 否
- 现象记录：

### STATUS

- 是否正常：是 / 否
- 现象记录：

### SELFTEST

- 是否正常：是 / 否
- 现象记录：

## RID 与参数命令测试结果

### RID,OK

- 是否正常：是 / 否
- 现象记录：

### RID,MISSING

- 是否正常：是 / 否
- 现象记录：

### RID,SUSPICIOUS

- 是否正常：是 / 否
- 现象记录：

### KP,0.60

- 是否正常：是 / 否
- 现象记录：

### KD,0.10

- 是否正常：是 / 否
- 现象记录：

### RESET

- 是否正常：是 / 否
- 现象记录：

## 模拟轨迹主线测试结果


GIMBAL,ACQUIRING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,90.00
STATE,HIGH_RISK,75.0
GIMBAL,ACQUIRING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,90.00
STATE,HIGH_RISK,75.0
Gimbal state changed to TRACKING
GIMBAL,TRACKING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,90.00
STATE,HIGH_RISK,75.0
GIMBAL,TRACKING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,101.95
STATE,HIGH_RISK,75.0
GIMBAL,TRACKING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,108.53
STATE,HIGH_RISK,75.0
GIMBAL,TRACKING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,112.15
STATE,HIGH_RISK,75.0
UPLINK,TRACK,node=A1,ts=625710,track=1,active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0,seen=30,lost=0
GIMBAL,TRACKING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0
DATA,100.00,114.13
STATE,HIGH_RISK,75.0
GIMBAL,TRACKING,track_active=1,confirmed=1,x=100.0,y=200.0,vx=0.0,vy=0.0

### TRACK,320,1800

- 是否正常：是 / 否
- 是否出现 `track_active=1`：是 / 否
- 是否出现 `confirmed=1`：是 / 否
- 是否出现 `UPLINK,TRACK`：是 / 否
- 是否进入 `TRACKING`：是 / 否
- 现象记录：

### TRACK,CLEAR

- 是否正常：是 / 否
- 是否成功回到空闲态：是 / 否
- 现象记录：

## 关键日志留存

### 启动日志示例

```text
```

### 空闲心跳示例

```text
```

### 状态快照示例

```text
```

### SELFTEST 示例

```text
```

### 模拟轨迹上行示例

```text
```

## 今日结论

- 今日测试是否通过：是 / 否
- 基础链路是否通过：是 / 否
- 模拟轨迹主线是否通过：是 / 否
- 当前程序是否适合进入下一阶段：是 / 否
- 当前主要问题：
- 今日确认可用的内容：
- 后续需要继续验证的内容：

## 后续动作

- 下一步计划 1：
- 下一步计划 2：
- 下一步计划 3：
