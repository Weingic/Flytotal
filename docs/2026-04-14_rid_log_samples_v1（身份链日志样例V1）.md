# 2026-04-14 身份正常/缺失/异常日志样例 V1

## 说明
以下样例为按当前固件字段整理的标准口径，用于联调时对照。

## 场景 A：身份正常（白名单命中）

输入示例：
```text
RID,MSG,SIM-RID-001,UAV,RID_SIM,1712880000000,VALID,WL_OK,-48
```

期望日志示例：
```text
RID,STATUS,node=A1,zone=ZONE_NORTH,rid_status=MATCHED,rid_whitelist_hit=1,rid_last_update_ms=523190,rid_last_match_ms=523194,rid_age_ms=4,rid_packet_valid=1,rid_id=SIM-RID-001,rid_device_type=UAV,rid_source=RID_SIM,rid_auth_status=VALID,rid_whitelist_tag=WL_OK,rid_signal_strength=-48,track_id=12,track_active=1,track_confirmed=1,timestamp=523194
BRIEF,main=TRACKING,track=12,active=1,confirmed=1,hunter=RID_MATCHED,gimbal=TRACKING,rid=MATCHED,rid_whitelist=1,rid_last_update_ms=523190,risk=18.0,risk_level=NORMAL,event_active=0,event_id=NONE,event_state=NONE,event_close_reason=NONE,x=320.0,y=1800.0
```

## 场景 B：身份缺失（无身份/超时）

输入示例：
```text
RID,CLEAR
```
或停止广播超过 `ReceiveTimeoutMs`。

期望日志示例：
```text
RID,STATUS,node=A1,zone=ZONE_NORTH,rid_status=NONE,rid_whitelist_hit=0,rid_last_update_ms=0,rid_last_match_ms=0,rid_age_ms=0,rid_packet_valid=0,rid_id=NONE,rid_device_type=NONE,rid_source=NONE,rid_auth_status=NONE,rid_whitelist_tag=NONE,rid_signal_strength=0,track_id=13,track_active=1,track_confirmed=1,timestamp=531002
RISK,STATUS,node=A1,zone=ZONE_NORTH,main_state=SUSPICIOUS,current_risk_state=SUSPICIOUS,pending_risk_state=SUSPICIOUS,risk_transition_mode=STABLE,risk_hold_ms=0,risk_hold_elapsed_ms=0,risk_score=49.0,risk_level=SUSPICIOUS,risk_base=10.0,risk_persistence=21.0,risk_confirmed=8.0,risk_rid=24.0,risk_proximity=0.0,risk_motion=0.0,risk_reasons=TRACK_PERSISTENT|TRACK_CONFIRMED|RID_NONE_OR_EXPIRED,track_id=13,track_active=1,track_confirmed=1,rid_status=NONE,rid_whitelist_hit=0,rid_last_update_ms=0,rid_last_match_ms=0,event_active=0,event_id=NONE,timestamp=531002
```

## 场景 C：身份异常（鉴权失败/白名单不通过）

输入示例：
```text
RID,MSG,SIM-RID-999,UAV,RID_SIM,1712880000000,INVALID,DENY,-45
```

期望日志示例：
```text
RID,STATUS,node=A1,zone=ZONE_NORTH,rid_status=INVALID,rid_whitelist_hit=0,rid_last_update_ms=536880,rid_last_match_ms=0,rid_age_ms=3,rid_packet_valid=1,rid_id=SIM-RID-999,rid_device_type=UAV,rid_source=RID_SIM,rid_auth_status=INVALID,rid_whitelist_tag=DENY,rid_signal_strength=-45,track_id=14,track_active=1,track_confirmed=1,timestamp=536883
EVENT,STATUS,node=A1,zone=ZONE_NORTH,main_state=HIGH_RISK,hunter_state=HIGH_RISK,gimbal_state=TRACKING,rid_status=INVALID,rid_whitelist_hit=0,rid_last_update_ms=536880,rid_last_match_ms=0,rid_id=SIM-RID-999,rid_source=RID_SIM,rid_auth_status=INVALID,rid_whitelist_tag=DENY,rid_signal_strength=-45,track_id=14,track_active=1,track_confirmed=1,risk_score=67.0,risk_level=HIGH_RISK,event_active=1,current_event_id=A1-0000536800-0005,event_id=A1-0000536800-0005,current_event_state=OPEN,current_event_close_reason=NONE
```

## 一键复现建议
```powershell
python tools/rid_broadcast_simulator_身份广播模拟器.py --port COM4 --mode normal
python tools/rid_broadcast_simulator_身份广播模拟器.py --port COM4 --mode missing --count 5
python tools/rid_broadcast_simulator_身份广播模拟器.py --port COM4 --mode invalid --count 10
```

## 2026-04-12 实测补充（risk_event_vision_chain_v1）

本次在 `Node_A_Base_Demo_V1.1` 实机跑通，关键日志如下（节选）：

```text
[PRECHECK] baseline=Node_A_Base_Demo_V1.1 (expected=Node_A_Base_Demo_V1.1), rid_status=NONE (normalized=NONE), ok=1
[PASS] scenario1_short_missing_rid_no_direct_event: PASS
[PASS] scenario2_sustained_missing_rid_risk_upgrade: PASS
[PASS] scenario3_legal_target_keep_low_risk: PASS
[PASS] scenario4_suspicious_rid_fast_risk_upgrade: PASS
[PASS] scenario5_high_risk_visual_capture_ready: PASS
[PASS] scenario6_track_lost_smooth_recover: PASS
Suite summary: passed=6, failed=0
```

对应 RID 新状态链路节选：

```text
RID,MISSING -> RID simulation updated: NONE
RID,OK -> RID simulation updated: MATCHED
RID,SUSPICIOUS -> RID simulation updated: INVALID
RISK,STATUS,...,rid_status=INVALID,...,risk_reasons=...|RID_INVALID
EVENT,STATUS,...,rid_status=NONE,...,risk_reasons=...|RID_NONE_OR_EXPIRED
```

## RID,MSG 主链自动验收命令（新增）

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite rid_identity_chain_v1 --boot-wait 8
```

通过标准（预期）：

```text
[PASS] scenario1_msg_valid_becomes_matched
[PASS] scenario2_msg_timeout_becomes_expired
[PASS] scenario3_msg_invalid_becomes_invalid
Suite summary: passed=3, failed=0
```

## 2026-04-13 实机执行结果（已通过）

执行命令：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite rid_identity_chain_v1 --boot-wait 8
```

关键输出（实机节选）：
```text
[PRECHECK] baseline=Node_A_Base_Demo_V1.1 (expected=Node_A_Base_Demo_V1.1), rid_status=NONE (normalized=NONE), ok=1
[PASS] scenario1_msg_valid_becomes_matched: PASS
[PASS] scenario2_msg_timeout_becomes_expired: PASS
[PASS] scenario3_msg_invalid_becomes_invalid: PASS
Acceptance report:
  suite=rid_identity_chain_v1 total=3 passed=3 failed=0
Suite summary: passed=3, failed=0
```

RID 关键状态证据（实机节选）：
```text
RID,STATUS,...,rid_status=MATCHED,...,rid_whitelist_hit=1,...,rid_auth_status=VALID,...,rid_whitelist_tag=WL_OK,...
RID,STATUS,...,rid_status=EXPIRED,...,rid_whitelist_hit=1,...,rid_packet_valid=1,...,rid_auth_status=VALID,...
RID,STATUS,...,rid_status=INVALID,...,rid_whitelist_hit=0,...,rid_auth_status=INVALID,...,rid_whitelist_tag=DENY,...
```
