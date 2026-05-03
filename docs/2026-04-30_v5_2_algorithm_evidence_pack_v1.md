# Flytotal v5.2 Algorithm Evidence Pack V1

Last updated: 2026-05-01

## 证据目标

v5.2 的每个创新点都要有代码或仿真证据对应，避免答辩时只停留在概念。

## 创新点与证据

| 创新点 | 代码位置 | 证据工具 |
| --- | --- | --- |
| 复杂环境下多模态融合 | `lib/Fusion/` | `tools/fusion_simulator.py --case far_mid_near` |
| LD2451 远距触发 | `lib/Ld2451Parser/` | 官方协议帧测试 + 10/30/50/80/100 m 实测 |
| 多旋翼特征筛选 | `lib/TrackManager/`, `lib/HunterAction/` | `tools/multirotor_classifier_验证.py --mock` |
| 云台预测 | `lib/GimbalPredictor/` | `tools/gimbal_prediction_simulator.py --lead-times 0,0.12,0.18` |
| 协同感知 | NodeB UART 字段 + ESP-NOW demo | `tools/co_sensing_simulator.py --scenario boundary_crossing` |

## 当前验收边界

- `100 m`: 只验收远距运动预警触发。
- 无 LD2451 数据：主循环继续运行，`ld2451_valid=0`。
- NodeB 掉线：NodeA 继续运行，`nodeb_online=0`。
- 非多旋翼目标：默认不直接进入 EVENT。
- 视觉：作为确认和证据固化，不作为唯一判定源。

## 推荐测试顺序

1. `pio run`
2. `pio run -d examples/nodeb_c3_identity_uart`
3. `FUSION,STATUS`
4. `FUSION,DEBUG`
5. `python tools/fusion_simulator.py --case far_mid_near`
6. `python tools/gimbal_prediction_simulator.py --lead-times 0,0.12,0.18`
7. `python tools/co_sensing_simulator.py --scenario boundary_crossing`
8. `python tools/multirotor_classifier_验证.py --mock`

## 给小白的解释

这是什么：一张“我不是只会讲概念，我真的有代码和数据”的证据清单。

有什么用：老师或评委问创新点时，你可以直接指到对应文件、仿真结果和实测项目。

你现在该怎么做：先跑仿真证据，硬件到位后按同一套字段补实测截图和视频。
