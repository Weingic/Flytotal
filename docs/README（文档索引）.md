# 文档索引

这份索引用来整理当前 `Flytotal/docs` 目录中的文档，方便你快速找到“协议说明、系统设计、测试工具、联调记录”对应的材料。

## 一、建议先看

如果你现在想先快速建立整体理解，建议按下面顺序阅读：

1. [2026-04-23_flytotal_guided_codewalk_01（全仓陪跑讲解01_总览与演进）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-23_flytotal_guided_codewalk_01（全仓陪跑讲解01_总览与演进）.md)
   面向初学者的全仓入口，先讲系统现在是什么、为什么会长成这样、应该按什么顺序读代码。
2. [2026-04-23_flytotal_guided_codewalk_02（全仓陪跑讲解02_固件主链）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-23_flytotal_guided_codewalk_02（全仓陪跑讲解02_固件主链）.md)
   把 `include/lib/src` 串成一条“输入 -> 轨迹 -> 风险 -> 云台 -> 事件 -> 上行”的主链，并补充设计思路。
3. [2026-04-23_flytotal_guided_codewalk_03（全仓陪跑讲解03_工具链与网页）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-23_flytotal_guided_codewalk_03（全仓陪跑讲解03_工具链与网页）.md)
   把 `tools`、网页和验收脚本讲成一个完整的外部支撑系统，解释为什么这些脚本是系统的一部分。
4. [1node_a_uplink_protocol（NodeA上行协议）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/1node_a_uplink_protocol（NodeA上行协议）.md)
   当前串口命令、状态输出和上行字段说明。
5. [3node_a_dataflow（NodeA数据流）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/3node_a_dataflow（NodeA数据流）.md)
   Node A 的主要数据流和模块关系。
6. [4node_a_state_machines（NodeA状态机）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/4node_a_state_machines（NodeA状态机）.md)
   关键状态机和行为切换逻辑。
7. [2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md)
   当前系统的整体功能图和逻辑梳理。

## 二、全仓陪跑讲解

- [2026-04-23_flytotal_guided_codewalk_01（全仓陪跑讲解01_总览与演进）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-23_flytotal_guided_codewalk_01（全仓陪跑讲解01_总览与演进）.md)
  从系统总览、能力演进、阅读顺序入手，帮助你先建立“全局地图”。
- [2026-04-23_flytotal_guided_codewalk_02（全仓陪跑讲解02_固件主链）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-23_flytotal_guided_codewalk_02（全仓陪跑讲解02_固件主链）.md)
  覆盖 `AppConfig.h`、`SharedData.h`、`lib/*`、`src/main.cpp`，按主链讲功能、设计、权衡。
- [2026-04-23_flytotal_guided_codewalk_03（全仓陪跑讲解03_工具链与网页）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-23_flytotal_guided_codewalk_03（全仓陪跑讲解03_工具链与网页）.md)
  覆盖 `tools/*` 和网页文件，解释桥接、视觉、验收、交付工具为什么存在。

## 三、基础设计文档

- [1node_a_uplink_protocol（NodeA上行协议）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/1node_a_uplink_protocol（NodeA上行协议）.md)
  Node A 当前对外串口协议说明。
- [2node_a_parameter_baseline（NodeA参数基线）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2node_a_parameter_baseline（NodeA参数基线）.md)
  当前核心参数的基线整理。
- [3node_a_dataflow（NodeA数据流）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/3node_a_dataflow（NodeA数据流）.md)
  模块间数据流、输入输出关系。
- [4node_a_state_machines（NodeA状态机）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/4node_a_state_machines（NodeA状态机）.md)
  云台与主流程的状态机说明。
- [9NodeA正式字段表文档（NodeA正式字段表）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/9NodeA正式字段表文档（NodeA正式字段表）.md)
  当前正式字段定义整理。
- [3.31低空节点与云端统一接口草案（低空节点与云端统一接口草案）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/3.31低空节点与云端统一接口草案（低空节点与云端统一接口草案）.md)
  节点与云端接口的阶段性草案。

## 四、测试工具与辅助文档

- [6node_a_single_board_troubleshooting（NodeA单板故障排查）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/6node_a_single_board_troubleshooting（NodeA单板故障排查）.md)
  单板调试时的常见问题排查。
- [7track_injector_usage（轨迹注入器使用说明）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/7track_injector_usage（轨迹注入器使用说明）.md)
  轨迹注入器的运行方法和常用参数。
- [8track_scenario_baseline（轨迹场景基线）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/8track_scenario_baseline（轨迹场景基线）.md)
  标准测试轨迹场景的固定基线。
- [10track_injector_source_walkthrough（轨迹注入器源码详解）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/10track_injector_source_walkthrough（轨迹注入器源码详解）.md)
  `track_injector_轨迹注入器.py` 的逐函数讲解、参数说明、状态流转和轨迹逻辑图。
- [10tool_chain_logic_map（工具链逻辑总图）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/10tool_chain_logic_map（工具链逻辑总图）.md)
  当前几份 Python 工具脚本之间的关系、总流程图、每个文件的功能分工和参数说明。
- [flytotal-beginner-logic-map（小白版总逻辑图）.html](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/diagrams/flytotal-beginner-logic-map（小白版总逻辑图）.html)
  小白版总图，先讲角色分工和一轮测试怎么走。
- [flytotal-parameter-glossary（参数词典）.html](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/diagrams/flytotal-parameter-glossary（参数词典）.html)
  参数词典，专门解释 `interval`、`hold-repeat`、`tracker`、`session` 这些词。
- [main-host-command-map（主机命令影响图）.html](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/diagrams/main-host-command-map（主机命令影响图）.html)
  设备命令影响图，专门解释 `TRACK / RID / STATUS / SELFTEST / RESET / KP / KD` 会影响什么。
- [main-cpp-beginner-diagram（小白版工人分工图）.html](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/diagrams/main-cpp-beginner-diagram（小白版工人分工图）.html)
  `main.cpp` 小白版工人分工图，把 `RadarTask / TrackingTask / CloudTask` 讲成 3 个工人的接力流程。

## 五、功能梳理与阶段总结

- [2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md)
  当前版本 Node A 的完整功能梳理。
- [2026-04-02_window_handoff_summary（窗口交接总结）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-02_window_handoff_summary（窗口交接总结）.md)
  阶段性交接材料。
- [2026-04-01_node_a_next_phase_plan（NodeA下一阶段计划）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-01_node_a_next_phase_plan（NodeA下一阶段计划）.md)
  下一阶段工作计划。

## 六、联调记录与更新记录

- [2026-04-01_node_a_radar_gimbal_integration_record（NodeA雷达云台联调记录）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-01_node_a_radar_gimbal_integration_record（NodeA雷达云台联调记录）.md)
  雷达与云台联调记录。
- [2026-04-01_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-01_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-01` 的功能更新记录。
- [2026-04-02_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-02_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-02` 的功能更新记录。
- [2026-04-03_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-03_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-03` 的功能更新记录。
- [2026-04-04_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-04_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-04` 的功能更新记录。
- [2026-04-05_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-05_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-05` 的功能更新记录。
- [2026-04-13_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-13` 基线收口日的功能更新记录。
- [2026-04-14_node_a_feature_updates（NodeA功能更新）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_node_a_feature_updates（NodeA功能更新）.md)
  `2026-04-14` 身份链接入日的功能更新记录。
- [5node_a_today_summary（NodeA当日总结）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/5node_a_today_summary（NodeA当日总结）.md)
  当日阶段总结。

## 七、4.13-4.14 关键交付

- [2026-04-13_hardware_issue_list_v1.1（硬件测试问题清单）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_hardware_issue_list_v1.1（硬件测试问题清单）.md)
- [2026-04-13_wiring_power_port_table_v1.1（接线供电端口表V1.1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_wiring_power_port_table_v1.1（接线供电端口表V1.1）.md)
- [2026-04-13_runtime_parameter_table_v1.1（可运行参数表V1.1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_runtime_parameter_table_v1.1（可运行参数表V1.1）.md)
- [2026-04-13_node_a_base_demo_v1.1（NodeA基线说明V1.1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_node_a_base_demo_v1.1（NodeA基线说明V1.1）.md)
- [2026-04-14_rid_data_structure_v1（RID数据结构定义）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_rid_data_structure_v1（RID数据结构定义）.md)
- [2026-04-14_rid_status_definition_v1（RID状态定义）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_rid_status_definition_v1（RID状态定义）.md)
- [2026-04-14_track_rid_matching_rules_v1（轨迹身份匹配规则V1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_track_rid_matching_rules_v1（轨迹身份匹配规则V1）.md)
- [2026-04-14_rid_log_samples_v1（身份链日志样例V1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_rid_log_samples_v1（身份链日志样例V1）.md)
- [2026-04-14_web_rid_display_acceptance_v1（网页RID展示验收V1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_web_rid_display_acceptance_v1（网页RID展示验收V1）.md)

## 八、历史单板测试记录

- [2026-03-30_esp32_single_board_checklist（ESP32单板检查清单）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-03-30_esp32_single_board_checklist（ESP32单板检查清单）.md)
  单板检查清单。
- [2026-03-30_esp32_single_board_record（ESP32单板记录）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-03-30_esp32_single_board_record（ESP32单板记录）.md)
  单板测试记录。

## 九、按用途找文档

如果你想查协议：

- 看 [1node_a_uplink_protocol（NodeA上行协议）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/1node_a_uplink_protocol（NodeA上行协议）.md)
- 看 [9NodeA正式字段表文档（NodeA正式字段表）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/9NodeA正式字段表文档（NodeA正式字段表）.md)

如果你想查系统逻辑：

- 看 [3node_a_dataflow（NodeA数据流）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/3node_a_dataflow（NodeA数据流）.md)
- 看 [4node_a_state_machines（NodeA状态机）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/4node_a_state_machines（NodeA状态机）.md)
- 看 [2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md)

如果你想查轨迹注入器：

- 看 [7track_injector_usage（轨迹注入器使用说明）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/7track_injector_usage（轨迹注入器使用说明）.md)
- 看 [8track_scenario_baseline（轨迹场景基线）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/8track_scenario_baseline（轨迹场景基线）.md)
- 看 [10track_injector_source_walkthrough（轨迹注入器源码详解）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/10track_injector_source_walkthrough（轨迹注入器源码详解）.md)

如果你想查联调与阶段记录：

- 看 [2026-04-01_node_a_radar_gimbal_integration_record（NodeA雷达云台联调记录）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-01_node_a_radar_gimbal_integration_record（NodeA雷达云台联调记录）.md)
- 看 [2026-04-01_node_a_next_phase_plan（NodeA下一阶段计划）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-01_node_a_next_phase_plan（NodeA下一阶段计划）.md)
- 看各日期的 `node_a_feature_updates` 文档
