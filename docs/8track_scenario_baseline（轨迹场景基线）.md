# 标准测试轨迹基线

日期：`2026-03-31`

本文档用于固定当前 `Node A` 无雷达联调时使用的标准轨迹场景，作为后续测试、复现、演示和材料整理的统一基线。

对应数据文件：
- [track_scenarios.json](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/tools/track_scenarios.json)

对应执行脚本：
- [track_injector_轨迹注入器.py](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/tools/track_injector_轨迹注入器.py)

## 一、基线目的

这份轨迹基线解决的问题是：

- 不再手工临时想轨迹点
- 不再把轨迹点写死在脚本逻辑里
- 后续每次测试都用同一组输入
- 便于多人协作、结果对比和问题复盘

## 二、当前标准场景

当前固定 3 组标准场景：

1. `left_to_right`
2. `right_to_left`
3. `enter_hold_leave`

## 三、场景 1：left_to_right

场景含义：
- 目标在固定距离下，从视场左侧向右侧穿越

用途：
- 验证横向跟踪是否连续
- 验证云台 `pan_angle` 是否随着 `x` 变化
- 验证 `UPLINK,TRACK` 是否持续更新

轨迹点：

```text
(-600,1800)
(-450,1800)
(-300,1800)
(-150,1800)
(0,1800)
(150,1800)
(300,1800)
(450,1800)
(600,1800)
```

预期现象：

- `track_active=1`
- `confirmed=1`
- 云台进入 `TRACKING`
- `DATA` 中 `pan_angle` 随 `x` 变化
- `UPLINK,TRACK` 持续输出

## 四、场景 2：right_to_left

场景含义：
- 目标在固定距离下，从视场右侧向左侧穿越

用途：
- 验证横向跟踪反向运动是否正常
- 验证脚本与主链对称性

轨迹点：

```text
(600,1800)
(450,1800)
(300,1800)
(150,1800)
(0,1800)
(-150,1800)
(-300,1800)
(-450,1800)
(-600,1800)
```

预期现象：

- 与 `left_to_right` 相同
- 只是 `x` 变化方向相反

## 五、场景 3：enter_hold_leave

场景含义：
- 目标沿中心线接近
- 在近距离保持一段时间
- 再逐步离开

用途：
- 验证距离变化对 `HunterAction` 和 `UPLINK,TRACK` 的影响
- 验证轨迹持续保持时系统是否稳定
- 验证清轨后系统是否能退出目标态

轨迹点：

```text
(0,2600)
(0,2300)
(0,2000)
(0,1700)
(0,1500)
(0,1500)
(0,1500)
(0,1500)
(0,1800)
(0,2200)
(0,2600)
```

预期现象：

- 目标进入后形成新轨迹
- `confirmed=1`
- `STATE` 输出保持稳定
- `UPLINK,TRACK` 持续更新 `y`
- `TRACK,CLEAR` 后最终触发 `TRACK_LOST`

## 六、当前默认执行参数

当前脚本默认参数为：

- `interval = 0.18s`
- `hold_repeat = 2`
- `settle = 1.5s`
- `boot_wait = 3.5s`

说明：

- `hold_repeat = 2` 可以让每个点重复发送两次，增强轨迹稳定性
- `settle = 1.5s` 用于在 `TRACK,CLEAR` 后观察系统退出
- `boot_wait = 3.5s` 用于等待 ESP32 启动完成后再发命令

## 七、推荐测试组合

### 组合 1：基础主链验证

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all
```

用途：
- 验证轨迹、云台、上行链是否整体可运行

### 组合 2：高风险验证

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all --rid MISSING
```

用途：
- 更容易观察 `HIGH_RISK`、`UPLINK,EVENT`、抓拍逻辑位

### 组合 3：合法目标验证

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --scenario all --rid OK
```

用途：
- 验证合法目标识别路径
- 观察 `RID_MATCHED` 状态

## 八、当前基线的意义

到这里为止，`2026-03-31` 这一天的“标准测试轨迹”已经不再只是脚本里的临时点列，而是正式变成了：

- 一份独立数据文件
- 一份可复用执行脚本
- 一份书面基线说明

这意味着后面：

- 你自己复测可以直接用
- 别人接手联调也能直接复现
- 材料里可以写“已建立标准轨迹场景库”

## 九、后续可扩展方向

后续可以继续扩展的场景包括：

- 低空盘旋
- 快速切入
- 靠近后急退
- 中心悬停
- 合法与非法目标混合切换

但在当前阶段，先保持这 3 组基线稳定即可。

