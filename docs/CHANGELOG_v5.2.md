# CHANGELOG v5.2

## 2026-05-08

### 稳定性补强

- 为 `RadarTask`、`NodeBTask`、`Ld2451Task`、`TrackingTask`、`CloudTask` 增加 ESP32 task watchdog 注册和喂狗。
- NodeB 串口增加掉线超时处理：超过 `3000ms` 未更新后标记 `OFFLINE_OR_TIMEOUT`，并按 `3000ms` 间隔重启 UART。
- 修正融合状态派生副作用：普通快照输出不再推进 `800ms` 高等级候选窗口，只有运行时更新才推进窗口。
- LD2451 数据超过 stale timeout 后自动失效，避免旧远距触发一直保留。
- 云台高级预测增加加速度限幅和低通滤波，降低轨迹噪声导致的二阶预测发散。

### 文档补强

- 新增 v5.2 总纲，把导师建议、系统架构、创新点和验收边界串起来。
- 新增硬件 BOM 与接线表，明确 NodeA/NodeB/LD2451 引脚和共地要求。
- 新增算法公式书，说明融合一致性、多旋翼筛选和云台预测公式。
- 新增现场 Runbook，覆盖编译、烧录、NodeA/NodeB、LD2451、视觉、证据生成和回退。
- 重写根目录 `README.md` 和 `docs/README（文档索引）.md`，修复乱码入口。

## 已有 v5.2 能力

- `FusionConfig::Enabled=false` 默认兼容基础验收，串口 `FUSION,ENABLE,1/0` 可运行时切换。
- `VISION,CONF,confidence=...,stability=...,state=...` 可以把视觉置信度注入主链融合。
- `FUSION,STATUS` 和 `FUSION,DEBUG` 输出融合阶段、等级、置信度、LD2451、NodeB、视觉质量。
- Dashboard 支持视觉红绿双框、协同感知状态和 v5.2 融合字段展示。
- 工具链支持融合新旧对比、云台预测对比、多旋翼特征输出和协同仿真。

## 仍然保留到后续版本

- 主链 ESP-NOW handoff 四态机。
- NodeB Wi-Fi OUI / NimBLE Remote ID 被动扫描。
- pyserial 双端 ESP-NOW 真实抓包统计。
- 证据 ZIP 一键打包工具。

## 给小白的解释

这份文件就是“为什么改、改了哪里”的账本。答辩时如果老师问 v5.2 和之前有什么差别，就按这里讲：更稳、更能解释、更能生成证据。
