# 2026-05-12 Demo Acceptance Record V1

## Summary

This record freezes the current Flytotal demo baseline after NodeA + physical
NodeB end-to-end validation.

- Branch: `feat/win-codex`
- NodeA: ESP32-S3 on `COM4`
- NodeB: ESP32-C3 on `COM6`
- Dashboard: `http://127.0.0.1:8765`
- NodeB demo RID: `SIM-RID-001 / VALID / WL_OK`
- NodeA whitelist result: `WL_ALLOWED`

`MOTION_ALERT` remains a far-motion warning only. The demo does not claim
stable 100 m drone identification.

## Evidence Artifacts

- Direct NodeA acceptance log:
  `outputs/e2e/demo_acceptance_after_nodeb_wl.log`
- Dashboard screenshot:
  `outputs/e2e/dashboard_demo_baseline.png`
- Restored live bridge log:
  `outputs/e2e/node_bridge_demo_baseline.log`
- Dashboard status source:
  `captures/e2e_node_status.json`

## Acceptance Results

### Physical NodeB Cooperative Baseline

Fresh evidence after flashing NodeB:

```text
nodeb_online=1
nodeb_status=OK
nodeb_node_id=B1
rid_status=RECEIVED
rid_id=SIM-RID-001
rid_source=NODEB_BLE
rid_auth_status=VALID
rid_whitelist_tag=WL_OK
rid_whitelist_hit=1
wl_status=WL_ALLOWED
event_active=0
RESULT,physical_nodeb_coop_baseline,PASS
```

This proves physical NodeB UART reaches NodeA and the real NodeB identity is
accepted by the whitelist chain.

### Physical NodeB Cooperative Target Closure

Fresh evidence with physical NodeB plus LD2451, track, and vision cues:

```text
nodeb_online=1
rid_status=MATCHED
rid_id=SIM-RID-001
wl_status=WL_ALLOWED
rid_whitelist_hit=1
ld2451_valid=1
far_motion_trigger=1
track_confirmed=1
target_verdict=CONFIRMED_COOPERATIVE_DRONE
risk_score=17.0
risk_level=NORMAL
event_active=0
RESULT,physical_nodeb_coop_target_closure,PASS
```

This proves a cooperative target is recognized as cooperative and does not open
an alarm event.

### Non-Cooperative Regression

Fresh evidence with hardware inputs disabled and denied RID injected:

```text
rid_status=INVALID
rid_id=SIM-RID-999
rid_auth_status=INVALID
rid_whitelist_tag=DENY
wl_status=WL_DENIED
ld2451_valid=1
far_motion_trigger=1
track_confirmed=1
target_verdict=VISUALLY_CONFIRMED_DRONE
risk_score=82.0
risk_level=EVENT
event_active=1
RESULT,noncoop_denied_target_closure,PASS
```

This proves non-cooperative targets still enter the risk/event closure.

## Current Restored Bench State

After acceptance, live inputs and the Dashboard bridge were restored.

```text
online=1
nodeb_online=1
nodeb_status=OK
rid_id=SIM-RID-001
rid_whitelist_tag=WL_OK
rid_whitelist_hit=1
wl_status=WL_ALLOWED
target_verdict=UNKNOWN_TARGET
event_active=0
```

`target_verdict=UNKNOWN_TARGET` is expected at idle because no target cue is
currently active.

## Next Camera Step

When the new UVC camera arrives:

1. Verify OpenCV can open the camera on Windows.
2. Adjust the 2.8-12 mm lens for clear mid/far target framing.
3. Confirm stable `vision_confidence`, `bbox_stability_score`, and
   `tracker_state=TRACKING`.
4. Re-run the cooperative and non-cooperative closures with real camera output
   instead of host-injected vision confidence.
