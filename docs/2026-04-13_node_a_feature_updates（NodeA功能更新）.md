# 2026-04-13 NodeA 功能更新（基线收口日）

## 今日目标
1. 硬件测试结果收口，不加大功能。
2. 冻结可继续开发的稳定基线。
3. 把问题分级、参数定版、接线口径定版、版本号定版。

## 今日新增交付文档
1. [2026-04-13_hardware_issue_list_v1.1（硬件测试问题清单）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_hardware_issue_list_v1.1（硬件测试问题清单）.md)
2. [2026-04-13_wiring_power_port_table_v1.1（接线供电端口表V1.1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_wiring_power_port_table_v1.1（接线供电端口表V1.1）.md)
3. [2026-04-13_runtime_parameter_table_v1.1（可运行参数表V1.1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_runtime_parameter_table_v1.1（可运行参数表V1.1）.md)
4. [2026-04-13_node_a_base_demo_v1.1（NodeA基线说明V1.1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-13_node_a_base_demo_v1.1（NodeA基线说明V1.1）.md)

## 今日冻结版本
`Node A Base Demo V1.1`

## 今日固件侧变更（为 4.14 预铺）
1. 新增基线版本字段：`NodeConfig::BaselineVersion = Node_A_Base_Demo_V1.1`。
2. `STATUS` / `SELFTEST` / 启动日志可输出 `baseline_version`，用于现场追溯。
3. RID 输出链预留了 `rid_whitelist_hit` 与 `rid_last_update_ms` 字段，供周二身份链直接接入。

## 今日结论
1. 基线参数、接线口径、问题清单、复测口径已冻结。
2. 周二可以直接进入 RID 身份接收链，不需要再回头做基线补课。

## 2026-04-13 晚间补充（4.8 标准化测试入口增强）

### 变更文件
1. `tools/acceptance_flow_411_单节点闭环验收流程.py`
2. `tools/acceptance_auto_411_快检全检自动验收.py`

### 本次能力增强
1. `acceptance_flow` 新增 `--suite-chain` 参数，支持一条命令串行执行多个 suite。
2. suite 串行执行结果会落入统一报告字段：`suite_names`、`suite_count`，并在 `step_results` 中明确每个 suite 的执行步骤名。
3. `acceptance_auto` 同步支持 `--suite-chain`，可在快检/全检模式下复用相同多套件链路。
4. `startup_helper` 同步支持 `--suite-chain`，生成的“快检/全检/自动验收”推荐命令统一携带同一套件链。

### 推荐用法（当前主推）
```powershell
python tools/acceptance_flow_411_单节点闭环验收流程.py --mode custom --run-suite --port COM4 --suite-chain rid_identity_chain_v1,risk_event_vision_chain_v1 --skip-usb --skip-closure --timeout-s 120
```

### 实测结果（本窗口）
1. 结果：`result=PASS`，`steps_total=3`，`steps_passed=3`，`steps_failed=0`。
2. 报告确认两套件都执行成功：
   - `track_injector_suite:rid_identity_chain_v1`
   - `track_injector_suite:risk_event_vision_chain_v1`
3. `startup_helper` 生成命令已带 `--suite-chain rid_identity_chain_v1,risk_event_vision_chain_v1`，可直接复制执行。

### 全量闭环复测（本窗口）
执行命令：
```powershell
python tools/acceptance_flow_411_单节点闭环验收流程.py --mode full --port COM4 --suite-chain rid_identity_chain_v1,risk_event_vision_chain_v1
```

实测结果：
1. `result=PASS`，`steps_total=5`，`steps_passed=5`，`steps_failed=0`。
2. `preflight_result=PASS`，`usb_result=PASS`，`closure_result=PASS`。
3. 关键闭环字段：
   - `closure_latest_event_id=A1-0000002622-0001`
   - `closure_export_count=1`
   - `closure_export_detail_ok=True`
