# 2026-05-16 Demo Submission Runbook V1

## Demo Scope

This demo submission focuses on the working end-to-end system, not the real
recognition dataset.

Ready for demo:

- NodeA status bridge
- NodeB identity chain
- real UVC camera bridge
- PC Dashboard
- cooperative target closure
- non-cooperative target closure
- event and evidence records
- target verdict display

Deferred:

- real drone dataset collection
- car dataset collection
- bird dataset collection
- measured real-world recognition accuracy

The correct claim is:

```text
The demo proves the end-to-end detection, identity check, fusion, alert,
evidence, and Dashboard workflow. Real labeled recognition metrics will be
measured after field data is collected.
```

Do not claim:

```text
100 m stable small-drone recognition has been fully proven.
```

## Existing Evidence

Use these files as proof that the current demo baseline already passed:

```text
docs/2026-05-16_real_camera_acceptance_record_v1.md
outputs/e2e/real_camera_coop_fusion.log
outputs/e2e/real_camera_noncoop_fusion.log
captures/latest_status.json
captures/e2e_node_status.json
```

Known passing results:

```text
CONFIRMED_COOPERATIVE_DRONE / NORMAL / event_active=0
VISUALLY_CONFIRMED_DRONE / EVENT / event_active=1
```

## Before The Demo

From the project root:

```powershell
git status --short --branch
pio run
```

Expected:

```text
branch is feat/win-codex
no unexpected code changes
build succeeds
```

## Start Demo Services

Start NodeA serial bridge:

```powershell
$nodeBridge = Get-ChildItem tools -Filter "node_a_serial_bridge_*.py" | Select-Object -First 1
python $nodeBridge.FullName --port COM4 --baud 115200 --output-file captures/e2e_node_status.json --echo
```

Start Dashboard:

```powershell
$web = Get-ChildItem tools -Filter "vision_web_server_*.py" | Select-Object -First 1
python $web.FullName --host 127.0.0.1 --port 8765
```

Start camera bridge:

```powershell
$vision = Get-ChildItem tools -Filter "vision_bridge_*.py" | Select-Object -First 1
python $vision.FullName --source 1 --backend dshow --tracker csrt --width 1280 --height 720 --status-file captures/latest_status.json
```

Open:

```text
http://127.0.0.1:8765
```

## Live Demo Order

1. Show NodeA online.
2. Show NodeB online.
3. Show camera frame and visual lock.
4. Show cooperative target result:

```text
rid_id=SIM-RID-001
rid_whitelist_tag=WL_OK
wl_status=WL_ALLOWED
target_verdict=CONFIRMED_COOPERATIVE_DRONE
risk_level=NORMAL
event_active=0
```

5. Show non-cooperative target result:

```text
rid_id=SIM-RID-999
rid_whitelist_tag=DENY
wl_status=WL_DENIED
target_verdict=VISUALLY_CONFIRMED_DRONE
risk_level=EVENT
event_active=1
```

6. Show Dashboard event detail:

```text
risk level
target verdict
RID status
whitelist status
LD2451 far motion
vision confidence
event id
evidence record
```

## If Real-Time Hardware Is Unstable

Use the existing accepted logs as fallback evidence:

```text
outputs/e2e/real_camera_coop_fusion.log
outputs/e2e/real_camera_noncoop_fusion.log
docs/2026-05-16_real_camera_acceptance_record_v1.md
```

Explain:

```text
The live demo is hardware-dependent, so the repository also contains frozen
acceptance logs from the real NodeA + NodeB + UVC camera setup.
```

## Dataset Question Answer

If asked why the dataset test is not included:

```text
The dataset stage is intentionally separated from the demo stage. The current
demo validates the system workflow and evidence chain. Real drone, car, and
bird labeled datasets require field access and will be collected next week.
Until then, the system does not claim measured 100 m drone-recognition accuracy.
```

## Submission Summary

Recommended one-sentence summary:

```text
This demo version completes the NodeA/NodeB/camera/Dashboard closed loop and
shows cooperative target suppression plus non-cooperative alert and evidence
recording; real recognition metrics are deferred to the scheduled field dataset
collection.
```
