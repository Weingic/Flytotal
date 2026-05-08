# CHANGELOG v5.2

## 2026-05-08 P0.2 稳定性补强

### 为什么改

v5.2 已经具备多模态融合、视觉置信度、NodeB 协同和 LD2451 远距触发，但现场演示会遇到更粗暴的问题：拔线、串口乱码、雷达异常值、换目标、长时间运行。P0.2 的目标是把这些“评委随手一试就能触发”的风险收住。

### 固件变化

- Watchdog timeout 从 `8s` 调整到 `12s`，保留 `PanicOnTimeout=true`。理由：现场串口、视觉桥接、Dashboard 同时运行时给任务调度留更多余量。
- `GimbalPredictor` 新增 motion reset，`GimbalController` 记录 `track_id`。理由：换目标时清掉旧目标速度/加速度，避免云台带着前一个目标的惯性继续外推。
- NodeB 增加 supervisor：掉线后清理在线状态、节点 ID、source、RSSI 和 NodeB 来源 RID；前 5 次快速重连，之后慢速退避。理由：避免 NodeB 永久离线时刷日志，也避免 Dashboard 显示旧身份链。
- Host、NodeB、LD2451 三路串口输入改为固定行缓冲。理由：减少 `String += char` 长时间运行造成的堆碎片。
- 雷达测量入口增加 `isfinite()` 和坐标范围守卫。理由：NaN/Inf 或超大坐标不能进入 TrackManager 和云台。
- LD2451 parser 增加协议合法性统计、字段范围校验和 `LD2451,SELFTEST`。理由：官方帧没有可用 CRC 字段，因此用长度、尾帧、字段合法性、连续帧确认降低串口干扰风险。
- LD2451 二进制数据需要连续 2 帧稳定后才写入主链；无目标帧可立即清除。理由：远距触发可以慢 1 帧，但不能被单帧毛刺带偏。

## 2026-05-08 P0 文档与基础稳定

- 为 `RadarTask`、`NodeBTask`、`Ld2451Task`、`TrackingTask`、`CloudTask` 增加 ESP32 task watchdog 注册和喂狗。
- 修正融合状态派生副作用：普通快照输出不再推进 `800ms` 高等级候选窗口，只有运行时更新才推进窗口。
- LD2451 数据超过 stale timeout 后自动失效，避免旧远距触发一直保留。
- 云台高级预测增加加速度限幅和低通滤波，降低轨迹噪声导致的二阶预测发散。
- 新增 v5.2 总纲、硬件 BOM、算法公式书、现场 Runbook 和证据目录索引。
- 重写根目录 README 和 docs 索引，修复乱码入口。

## v5.2 主能力索引

| 能力 | 关键入口 | 答辩价值 |
| --- | --- | --- |
| 默认兼容基础验收 | `FusionConfig::Enabled=false` | 基础六场景不被高级融合回归影响 |
| 运行时开启融合 | `FUSION,ENABLE,1/0` | demo 前手动开启 v5.2 |
| 视觉置信度进主链 | `VISION,CONF,...` | 证明视觉不是只在网页上显示 |
| LD2451 远距触发 | `LD2451,SELFTEST` / 二进制串口 | 支撑 10/30/50/80/100m 远距预警测试 |
| NodeB 协同节点 | NodeB UART + Dashboard 协同视图 | 支撑 ESP32 边缘节点和协同感知创新点 |
| 多旋翼筛选 | `TrackManager` 特征评分 | 支撑抗干扰和非无人机过滤 |
| 云台预测 | `GimbalPredictor` 二阶外推 | 支撑实时跟踪和预测能力 |

## 后续保留项

- 主链 ESP-NOW handoff 四态机。
- NodeB Wi-Fi OUI / NimBLE Remote ID 被动扫描。
- pyserial 双端 ESP-NOW 真实抓包统计。
- 证据 ZIP 一键打包工具。

## 给小白的解释

这份文件是“为什么改、改了哪里”的账本。答辩时如果老师问 v5.2 和之前有什么差别，就按这里讲：先把系统跑稳，再把多源融合、远距预警、视觉确认和协同节点说清楚。
