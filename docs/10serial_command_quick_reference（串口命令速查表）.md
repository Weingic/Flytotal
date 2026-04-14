# 串口命令速查表

## 1. 现在最推荐你记住的命令
后面先只记这一组就够了：

```text
HELP
BRIEF
STATUS
RISK,STATUS
EVENT,STATUS
LASTEVENT
RESET
DEBUG,OFF
UPLINK,OFF
TRACK,x,y
TRACK,CLEAR
RID,OK
RID,MISSING
RID,SUSPICIOUS
```

这一组命令已经能覆盖你当前 80% 以上的联调操作。

## 2. 每条命令是干什么的

### 2.1 `HELP`
作用：
- 查看全部串口命令入口
- 不再靠自己硬记

推荐场景：
- 忘了命令名时先输这一条

### 2.2 `BRIEF`
作用：
- 输出一条极简状态
- 只看主状态、轨迹、风险、事件、关闭原因

适合现在这种情况：
- 输出太长
- 不想看几十个字段

重点字段：
- `main`
- `track`
- `active`
- `confirmed`
- `risk`
- `risk_level`
- `event_active`
- `event_state`
- `event_close_reason`

### 2.3 `STATUS`
作用：
- 看完整一点的当前总状态

什么时候用：
- `BRIEF` 看出异常后，再用它补充细节

### 2.4 `RISK,STATUS`
作用：
- 专门看风险评分和风险状态

重点只看：
- `risk_score`
- `current_risk_state`
- `pending_risk_state`
- `risk_transition_mode`

### 2.5 `EVENT,STATUS`
作用：
- 专门看事件对象当前状态

重点只看：
- `event_active`
- `current_event_state`
- `current_event_close_reason`
- `current_event_id`

### 2.6 `LASTEVENT`
作用：
- 看最近一次事件快照

注意：
- 目前它不是最稳定的验收依据
- 当前更可靠的是 `EVENT,STATUS.current_event_close_reason`

### 2.7 `RESET`
作用：
- 把系统回到干净状态

推荐习惯：
- 每次正式测试前先执行一次

### 2.8 `DEBUG,OFF`
作用：
- 关闭大量调试刷屏

### 2.9 `UPLINK,OFF`
作用：
- 关闭 `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` 长串输出

推荐搭配：
```text
DEBUG,OFF
UPLINK,OFF
```

这样串口会干净很多。

### 2.10 `TRACK,x,y`
作用：
- 手工注入一帧模拟轨迹

示例：
```text
TRACK,320,1800
```

### 2.11 `TRACK,CLEAR`
作用：
- 清除当前模拟轨迹

### 2.12 `RID,OK / RID,MISSING / RID,SUSPICIOUS`
作用：
- 手工切换身份状态

最常用的是：
```text
RID,OK
RID,MISSING
```

## 3. 推荐操作顺序

### 3.1 平时手工查看
```text
DEBUG,OFF
UPLINK,OFF
BRIEF
RISK,STATUS
EVENT,STATUS
```

### 3.2 手工做一个最简单模拟
```text
RESET
DEBUG,OFF
UPLINK,OFF
TRACK,320,1800
RID,MISSING
BRIEF
RISK,STATUS
EVENT,STATUS
```

### 3.3 长流程不要手敲
像 `4.7` 这种连续轨迹确认、风险升级、风险回落、事件关闭的流程：

不要靠手工串口敲。

直接用脚本：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --validate-47
```

## 4. 以后怎么看输出
以后不要一上来读整行长串。

先分三层：

### 第一层：先看 `BRIEF`
它告诉你：
- 现在主状态是什么
- 轨迹是不是活跃
- 风险大不大
- 事件是不是打开
- 事件是怎么关闭的

### 第二层：需要风险细节时看 `RISK,STATUS`
只盯风险，不看别的。

### 第三层：需要事件细节时看 `EVENT,STATUS`
只盯事件，不看别的。

## 5. 当前最重要的经验
你现在不用强迫自己把所有串口命令和所有字段都记住。

对当前阶段来说：
- 手工查看靠 `HELP + BRIEF + RISK,STATUS + EVENT,STATUS`
- 连续验收靠脚本

这样你的操作压力会小很多，后面也更不容易乱。
