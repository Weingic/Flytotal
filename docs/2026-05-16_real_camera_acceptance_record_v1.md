# 2026-05-16 Real Camera Acceptance Record V1

## Summary

This record freezes the first real UVC camera acceptance pass for the Flytotal
NodeA + NodeB demo baseline.

- Branch: `feat/win-codex`
- NodeA: ESP32-S3 on `COM4`
- NodeB: ESP32-C3 on `COM6`
- Camera source: `source=1`
- Camera backend: `dshow`
- Tracker: `CSRT`
- Dashboard: `http://127.0.0.1:8765`

The result proves that the real camera can provide a stable visual lock for the
current fusion demo. It does not claim stable 100 m drone identification.

## Evidence Artifacts

- Cooperative closure log:
  `outputs/e2e/real_camera_coop_fusion.log`
- Non-cooperative closure log:
  `outputs/e2e/real_camera_noncoop_fusion.log`
- Vision status source:
  `captures/latest_status.json`
- NodeA status source:
  `captures/e2e_node_status.json`

## Camera Readiness

The real camera bridge was switched from `source=0` to `source=1` after the
first source showed the wrong camera feed.

Fresh vision status:

```text
source=1
source_ready=1
vision_state=VISION_LOCKED
vision_locked=1
vision_confidence=0.8
bbox_stability_score=0.8
tracker_state=TRACKING
```

This proves OpenCV can read the selected UVC camera and the CSRT tracker can
hold the selected ROI.

## Cooperative Target Closure

Fresh evidence using physical NodeB whitelist identity and the real camera
visual lock:

```text
nodeb_online=1
nodeb_status=OK
rid_status=MATCHED
rid_id=SIM-RID-001
rid_whitelist_tag=WL_OK
rid_whitelist_hit=1
wl_status=WL_ALLOWED
ld2451_valid=1
far_motion_trigger=1
vision_confidence=0.80
bbox_stability_score=0.80
tracker_state=TRACKING
target_verdict=CONFIRMED_COOPERATIVE_DRONE
risk_score=17.0
risk_level=NORMAL
event_active=0
RESULT,real_camera_coop_fusion,PASS
```

This proves a cooperative target remains non-alarming when the real camera
visual chain is active.

## Non-Cooperative Target Closure

Fresh evidence using a denied RID identity and the real camera visual lock:

```text
rid_status=INVALID
rid_id=SIM-RID-999
rid_auth_status=INVALID
rid_whitelist_tag=DENY
rid_whitelist_hit=0
wl_status=WL_DENIED
ld2451_valid=1
ld2451_range_m=50.00
ld2451_speed_mps=1.20
far_motion_trigger=1
vision_state=VISION_LOCKED
vision_locked=1
vision_confidence=0.80
bbox_stability_score=0.80
tracker_state=TRACKING
target_verdict=VISUALLY_CONFIRMED_DRONE
risk_score=82.0
risk_level=EVENT
event_active=1
event_id=A1-0000004657-0001
RESULT,real_camera_noncoop_fusion,PASS
```

This proves a non-cooperative target can enter the visual-confirmed event
closure with real camera evidence.

## Restored Bench State

After the tests, live inputs and the Dashboard bridge were restored.

```text
nodeb_online=1
nodeb_status=OK
rid_status=RECEIVED
rid_id=SIM-RID-001
rid_whitelist_tag=WL_OK
rid_whitelist_hit=1
wl_status=WL_ALLOWED
target_verdict=UNKNOWN_TARGET
event_active=0
```

`target_verdict=UNKNOWN_TARGET` is expected at idle because no target cue is
active.

## Next Data Step

Start real dataset collection with the same sensor fields already used by
`datasets/drone_recognition/sample_tracks.csv`.

Recommended first labels:

```text
drone
person
bird
car
clutter
```

Run the existing multirotor classifier script:

```powershell
python tools/<multirotor_classifier_script>.py --input datasets/drone_recognition/sample_tracks.csv --output-dir outputs/drone_recognition --min-accuracy 0.80 --min-recall 0.80
```

When real data replaces the sample CSV, report the measured accuracy and recall
as evidence, even if the first result is below target.
