# 2026-04-14 NodeA 功能更新（身份链接入日）

## 今日目标
1. 定义并冻结 RID 数据结构。
2. 接入 RID 状态机：`RID_NONE / RID_RECEIVED / RID_MATCHED / RID_EXPIRED / RID_INVALID`。
3. 打通轨迹-身份匹配窗口与超时机制。
4. 让网页端可直接看到 `rid_status`、白名单命中与最近身份更新时间。

## 今日代码改动点
1. `include/SharedData.h`
   - 增加 RID 元数据字段：`rid_whitelist_hit`、`rid_last_update_ms`、`rid_last_match_ms` 等。
2. `include/AppConfig.h`
   - 新增 `RidConfig::MatchWindowMs / ReceiveTimeoutMs`。
3. `lib/HunterAction/HunterAction.cpp`
   - 按新 RID 状态映射风险评分。
4. `src/main.cpp`
   - 增加 `RID,MSG` / `RID,STATUS` / `RID,CLEAR`。
   - 增加身份包解析、白名单判定、匹配窗口和超时判定。
   - 输出链透传 RID 细节字段。
5. `tools/node_a_serial_bridge_NodeA串口桥接.py`
   - 增加 RID 新字段映射。
6. `tools/vision_dashboard.html`
   - 新增 RID 白名单与 RID 最近更新时间展示。
7. `tools/rid_broadcast_simulator_身份广播模拟器.py`
   - 新增临时身份广播脚本（Node B 未就绪时用于联调）。
8. `tools/track_injector_轨迹注入器.py`
   - 新增 RID 状态归一化校验层：`MISSING -> NONE`、`SUSPICIOUS -> INVALID`。
   - 验收脚本参数扩展为兼容新旧 RID 状态（保持旧命令可用，适配 V1.1 新输出）。
9. `tools/track_injector_轨迹注入器.py` + `src/main.cpp`
   - 新增 suite/validate 运行前预检：读取 `STATUS` 与 `RID,STATUS`，强校验 `baseline_version=Node_A_Base_Demo_V1.1`。
   - 预检不通过默认阻断，并打印 `issues`（可用 `--allow-baseline-mismatch` 临时放行）。
   - 串口 `HELP` 与 RID 错误提示改为“新状态优先，旧状态别名兼容”。
10. `src/main.cpp`
   - 修复 `STATUS` 命令触发 `Track_Task` 栈溢出风险：将 `Track_Task` 栈从 `6144` 提升到 `12288`（最小行为变更，仅稳态加固）。
11. `tools/track_injector_轨迹注入器.py`
   - 将预检结果 `precheck` 固化写入 `latest_test_session.json`，即使 suite 通过也能追溯本次基线核验结果。
12. `tools/track_injector_轨迹注入器.py`
   - 新增 `rid_identity_chain_v1` 套件，专测 `RID,MSG` 主链三种关键状态：
     - `VALID + WL_OK -> MATCHED`
     - 超时 -> `EXPIRED`
     - `INVALID + DENY -> INVALID`

## 推荐联调命令（V1.1）
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --boot-wait 8
```
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite rid_identity_chain_v1 --boot-wait 8
```
如遇到预检临时误拦截，可应急放行：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --boot-wait 8 --allow-baseline-mismatch
```

## 2026-04-12 实机验收结论（补记）
1. 预检通过：`baseline=Node_A_Base_Demo_V1.1`，`rid_status=NONE`，`ok=1`。
2. `risk_event_vision_chain_v1`：`passed=6, failed=0`。
3. RID 状态链路已按新口径运行：`NONE / MATCHED / INVALID`。

## 2026-04-13 实机补充闭环（按窗口交接第 6 步）
1. 已完成 `rid_identity_chain_v1` 实机执行（用户现场日志已确认）：
   - 命令：`python tools/track_injector_轨迹注入器.py --port COM4 --suite rid_identity_chain_v1 --boot-wait 8`
   - 预检：`baseline=Node_A_Base_Demo_V1.1`，`rid_status=NONE`，`ok=1`
   - 结果：`suite=rid_identity_chain_v1 total=3 passed=3 failed=0`
2. 已完成 `risk_event_vision_chain_v1` 回归复测（本窗口实机重跑）：
   - 命令：`python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --boot-wait 8`
   - 预检：`baseline=Node_A_Base_Demo_V1.1`，`rid_status=NONE`，`ok=1`
   - 结果：`suite=risk_event_vision_chain_v1 total=6 passed=6 failed=0`
3. 本轮结论：
   - 身份链专项与主链回归均 PASS。
   - 可按计划进入下一日期计划项，不在当前小点反复打磨。

## 今日新增交付文档
1. [2026-04-14_rid_data_structure_v1（RID数据结构定义）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_rid_data_structure_v1（RID数据结构定义）.md)
2. [2026-04-14_rid_status_definition_v1（RID状态定义）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_rid_status_definition_v1（RID状态定义）.md)
3. [2026-04-14_track_rid_matching_rules_v1（轨迹身份匹配规则V1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_track_rid_matching_rules_v1（轨迹身份匹配规则V1）.md)
4. [2026-04-14_rid_log_samples_v1（身份链日志样例V1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_rid_log_samples_v1（身份链日志样例V1）.md)
5. [2026-04-14_web_rid_display_acceptance_v1（网页RID展示验收V1）.md](C:/Users/WZwai/Documents/PlatformIO/Projects/Flytotal/docs/2026-04-14_web_rid_display_acceptance_v1（网页RID展示验收V1）.md)

## 今日结论
系统已从“只看见目标”升级到“可做初步身份合规核验”的联调阶段。
