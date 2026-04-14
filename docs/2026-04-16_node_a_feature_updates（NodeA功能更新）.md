# 2026-04-16 NodeA 功能更新（雷达-云台-视觉融合链 V1）

## 今日目标
1. 固化雷达到云台映射规则（粗对准优先）。
2. 固化视觉子状态定义。
3. 明确视觉如何参与主链与事件证据。
4. 网页端可观测 vision 字段。

## 当前已具备能力
1. 主链输出已带：`vision_state` / `vision_locked` / `capture_ready`。
2. 网页端已显示 vision 状态。
3. 风险与事件链可与视觉字段同屏联调。

## 本轮文档冻结
1. `docs/2026-04-16_radar_gimbal_mapping_rule_v1（雷达到云台映射规则V1）.md`
2. `docs/2026-04-16_vision_state_definition_v1（视觉状态定义V1）.md`
3. `docs/2026-04-16_vision_mainchain_integration_rules_v1（视觉参与主链规则V1）.md`

## 现场验收口径
1. 雷达发现目标 -> 云台转向目标区域。
2. 视觉进入 `SEARCHING -> LOCKED`（或可解释的 `LOST`）。
3. 高风险/事件态触发抓拍增强。
4. 网页可稳定看到 `vision_state/vision_locked/capture_ready`。

## 暂不推进项
1. 暂不训练复杂模型。
2. 暂不做通用无人机识别大模型路线。
3. 先闭环，再精度优化。

## 2026-04-13 实机证据补记（4.16 验收口径对应）
1. 串口桥接已连接并持续采样：
   - `Connected to COM4 at 115200`
   - 会话日志、事件快照、联合证据、验收快照均已写入 `captures/`
2. `risk_event_vision_chain_v1` 套件通过：
   - `suite=risk_event_vision_chain_v1 total=6 passed=6 failed=0`
3. 视觉链关键场景通过：
   - `scenario5_high_risk_visual_capture_ready: PASS`
   - 字段证据：`vision_state=VISION_LOCKED`、`vision_locked=1`、`capture_ready=1`
4. 状态回落场景通过：
   - `scenario6_track_lost_smooth_recover: PASS`
   - 字段证据：`main_state=LOST`、`current_event_state=CLOSED`、`current_event_close_reason=TRACK_LOST`

## 本次证据文件
1. `captures/latest_joint_chain_evidence.json`
2. `captures/latest_acceptance_snapshot.json`
3. `captures/latest_node_events.json`
4. `captures/session_logs/*.jsonl`

## 2026-04-13 工具链加固补记（4.16 口径继续推进）
1. 新增“视觉运行态门禁”到预检：
   - 文件：`tools/preflight_411_环境预检.py`
   - 检查项：`latest_status.json` 新鲜度 + `source_ready/tracker_ready/vision_chain_ready`
   - 新参数：`--skip-vision-runtime-check`、`--vision-status-file`、`--vision-max-stale-ms`
2. 预检输出新增关键字段：
   - `vision_runtime_ready`
   - `vision_status_stale_age_ms`
   - `can_run_acceptance`（用于控制是否允许进入验收）
3. 启动助手与验收流已接入门禁失败提示：
   - 若视觉桥未就绪，建议优先运行：
   - `python tools/vision_bridge_视觉桥接.py --backend dshow --source 0 --tracker csrt --tracker-fallback auto --source-warmup-frames 12`
4. 修复历史乱码路径/文案导致的问题：
   - 统一脚本名寻址为“前缀发现”方式，降低中文文件名编码差异带来的失败概率
   - 修复 `startup_helper` 控制台编码报错（GBK）并改为稳定 ASCII 终端标签

## 2026-04-14 验收关卡补记（4.16 继续推进）
1. 单节点证据闭环核对新增“视觉证据门禁”：
   - 文件：`tools/single_node_evidence_closure_check_单节点证据闭环核对.py`
   - 新参数：`--require-vision-lock`、`--min-vision-lock-hits`、`--require-capture-ready`、`--min-capture-ready-hits`
   - 新失败项：`vision_lock_evidence_below_min`、`capture_ready_evidence_below_min`
2. 验收总流程已接入视觉证据门禁：
   - 文件：`tools/acceptance_flow_411_单节点闭环验收流程.py`
   - `--mode full` 默认启用：
     - `closure_require_vision_lock=true`
     - `closure_require_capture_ready=true`
3. 验收报告新增可观测字段：
   - `closure_vision_lock_hits`
   - `closure_capture_ready_hits`
   - `closure_vision_lock_ok`
   - `closure_capture_ready_ok`
4. 失败时下一步建议更准确：
   - 优先提示先起网页服务，再提示视觉桥与锁定动作，不再只给笼统建议
5. 自动验收总报告同步显示视觉门禁结果：
   - 文件：`tools/acceptance_auto_411_快检全检自动验收.py`
   - 新输出：
     - `full_closure_vision_lock_hits`
     - `full_closure_capture_ready_hits`
     - `full_closure_vision_lock_ok`
     - `full_closure_capture_ready_ok`

## 2026-04-14 交付门禁补记（4.16 继续推进）
1. 交付就绪核对脚本已接入 4.11 验收报告：
   - 文件：`tools/delivery_bundle_readiness_check_交付包就绪核对.py`
   - 新输入：
     - `captures/latest_411_acceptance_auto_report.json`
     - `captures/latest_411_acceptance_full_report.json`
2. 交付核对新增视觉证据强校验（默认开启）：
   - 参数：`--require-vision-evidence`（默认 true）
   - 判定字段：
     - `closure_vision_lock_ok` + `closure_vision_lock_hits`
     - `closure_capture_ready_ok` + `closure_capture_ready_hits`
3. 交付报告新增可观测检查项：
   - `checks.acceptance_ok`
   - `checks.vision_evidence_ok`
4. 意义：
   - 防止“验收步骤看起来通过，但未形成视觉锁定/抓拍证据”的伪通过进入交付包。
