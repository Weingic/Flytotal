# 自动轨迹注入脚本使用说明

脚本文件：
- [track_injector_轨迹注入器.py](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/tools/track_injector_轨迹注入器.py)

场景数据文件：
- [track_scenarios.json](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/tools/track_scenarios.json)

## 作用

该脚本用于在不接雷达的情况下，自动向 `Node A` 发送标准 `TRACK,x,y` 序列，帮助你完成模拟轨迹主链联调。

支持的标准场景：

- `left_to_right`
- `right_to_left`
- `enter_hold_leave`

说明：
- 当前轨迹点列已经从脚本中抽离到独立 `json` 文件，后续修改标准场景时优先改数据文件，不要直接改脚本逻辑。

## 基本用法

运行全部场景：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all
```

只运行左到右穿越：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario left_to_right
```

只运行进入-停留-离开：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario enter_hold_leave
```

## 可选参数

设置 RID 状态：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all --rid MISSING
```

调整发送间隔：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all --interval 0.15
```

调整每个点重复发送次数：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all --hold-repeat 3
```

## 预期现象

运行脚本后，串口应出现：

- `track_active=1`
- `confirmed=1`
- `UPLINK,TRACK`
- `GIMBAL,TRACKING`

场景结束并发送 `TRACK,CLEAR` 后，应逐步回到空闲状态。

## 当前建议

首测建议先用：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all --rid MISSING
```

因为：
- 三个标准场景都会跑到
- `RID=MISSING` 更容易观察风险状态和事件输出

