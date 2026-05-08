# Flytotal 文档索引

这份索引用来给 v5.2 答辩和实测找入口。历史文档仍保留在 `docs/`，但现在建议优先看下面几份。

## v5.2 必读

1. [v5.2 总纲](2026-05-08_v5_2_overall_upgrade_v1.md)：把导师建议、系统目标、架构、测试边界串起来。
2. [硬件 BOM 与接线](2026-05-08_hardware_bom_wiring_v1.md)：NodeA、NodeB、LD2450、LD2451、摄像头、供电和引脚表。
3. [算法公式书](2026-05-08_algorithm_formula_book_v1.md)：融合一致性、多旋翼筛选、云台预测公式。
4. [v5.2 现场 Runbook](2026-05-08_v5_2_runbook_v1.md)：编译、烧录、测试、故障回退步骤。
5. [v5.2 变更记录](CHANGELOG_v5.2.md)：从 v1.0/v5.1 到 v5.2 的变更理由。
6. [v5.2 答辩素材](2026-05-03_defense_v5_2_答辩素材.md)：创新点、证据图、录屏路径和 Q&A。

## 测试顺序

1. `pio run` 和 NodeB 工程编译。
2. NodeA 单板串口命令：`CONFIG,STATUS`、`FUSION,STATUS`、`FUSION,ENABLE,1/0`。
3. NodeA + NodeB 串口联调，验证 `nodeb_online` 掉线恢复。
4. LD2451 文本仿真，再做 `10m/30m/50m/80m/100m` 远距触发记录。
5. 视觉桥接和 Dashboard 红绿双框。
6. 证据工具生成融合对比、云台预测、多旋翼特征图。

## 仓库入口

- 主固件：`src/main.cpp`、`include/AppConfig.h`、`include/SharedData.h`
- 算法模块：`lib/Fusion/`、`lib/Ld2451Parser/`、`lib/TrackManager/`、`lib/GimbalPredictor/`
- NodeB 示例：`examples/nodeb_c3_identity_uart/`
- 大屏和工具：`tools/vision_dashboard.html`、`tools/*simulator*.py`
- 答辩证据索引：`docs/algorithm_evidence/README.md`
