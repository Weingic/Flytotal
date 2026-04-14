# 2026-04-15 NodeA 功能更新（白名单链 + 合法目标闭环）

## 今日目标
1. 建立白名单配置与状态定义。
2. 打通合法目标主链（合法不报警）。
3. 建立身份异常与超时回落规则。
4. 网页端区分合法/可疑/高危。

## 本轮代码落地
1. `include/SharedData.h`
   - 新增 `WhitelistStatus`：`WL_UNKNOWN/WL_ALLOWED/WL_DENIED/WL_EXPIRED`。
   - 在 `SystemData` / `UnifiedOutputSnapshot` / `EventObject` 中新增白名单字段。
2. `include/AppConfig.h`
   - 新增 `RidConfig::LegalHoldMs=2000`、`RidConfig::ReconfirmWindowMs=1200`。
3. `lib/HunterAction/HunterAction.h/.cpp`
   - 风险评估与状态更新接入 `wl_status`。
   - `WL_ALLOWED` 进入低风险合法链；`WL_DENIED/WL_EXPIRED` 不放行。
4. `src/main.cpp`
   - 内置白名单配置表与判定逻辑。
   - `refreshRidRuntime` 接入合法保持、再确认窗口、回落逻辑。
   - 串口输出新增 `wl_*` 字段。
   - 新增命令：`WL,STATUS` / `WL,LIST`。
5. `tools/node_a_serial_bridge_NodeA串口桥接.py`
   - 增加 `wl_status/wl_owner/wl_label/wl_expire_time_ms/wl_note` 字段映射和默认值。
6. `tools/vision_dashboard.html`
   - Node 卡片 `Hunter` 改为策略色块：
     - 绿色：合法链
     - 黄色：可疑/待确认
     - 橙红：高风险/事件
   - `RID 白名单` 改为状态色块（ALLOWED/DENIED/EXPIRED/UNKNOWN）。

## 新增文档交付
1. `docs/2026-04-15_whitelist_configuration_table_v1（白名单配置表V1）.md`
2. `docs/2026-04-15_legal_illegal_judgement_rules_v1（合法非法判定规则V1）.md`
3. `docs/2026-04-15_rid_timeout_fallback_rules_v1（身份超时与回落规则V1）.md`

## 本地验证
1. 固件编译：`platformio run` 通过。
2. Python 语法：
   - `python -m py_compile tools/node_a_serial_bridge_NodeA串口桥接.py` 通过。
   - 验收流脚本 `py_compile` 通过。

## 待现场验收（实机）
1. 合法目标持续存在：不进入高危事件。
2. 无身份目标：进入可疑链。
3. 有身份但不在白名单：不放行。
4. 合法目标短时丢身份后恢复：不瞬时误报警。
