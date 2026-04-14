# 2026-04-17 状态报文与事件报文格式 V1

## 目标
固定上行报文口径，保证“状态监控”和“事件证据”分层清晰。

## 状态报文（UPLINK,HB / TRACK）
最少字段：
1. 轨迹：`track_id/track_active/track_confirmed/x/y/vx/vy`
2. 主链：`main_state/hunter_state/gimbal_state`
3. 身份：`rid_status/rid_id/rid_auth_status/rid_whitelist_hit/wl_status`
4. 风险：`risk_score/risk_level/risk_reasons/trigger_flags`
5. 视觉：`vision_state/vision_locked/capture_ready`

## 事件报文（UPLINK,EVENT）
最少字段：
1. 事件标识：`event_id/event_status/event_level/reason/event_close_reason`
2. 目标上下文：`track_id/x/y`
3. 事件判据：`risk_score/risk_level/risk_reasons/trigger_flags/event_trigger_reasons`
4. 身份白名单：`rid_status/rid_whitelist_hit/wl_status`
5. 视觉证据：`vision_state/vision_locked/capture_ready`

## 对齐说明
1. 网页详情使用 `event_object_v1` 做展示主对象。
2. 导出证据 JSON 保留原始事件记录 + 标准对象，便于回放与审计。
