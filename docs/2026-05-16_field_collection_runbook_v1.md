# 2026-05-16 Field Collection Runbook V1

## Purpose

This runbook freezes the preparation work for next week's real target
collection. It keeps the current demo claim conservative:

- completed: NodeA + NodeB + real UVC camera end-to-end closure
- completed: cooperative and non-cooperative logic acceptance
- completed: real track CSV collector
- deferred: real drone, car, bird field samples

Do not claim stable real-drone recognition until real labeled data is collected
and measured.

## What Can Be Done Before Field Access

1. Keep the software baseline frozen on `feat/win-codex`.
2. Keep `datasets/drone_recognition/sample_tracks.csv` as the format example.
3. Use `datasets/drone_recognition/real_tracks.csv` only as a local field file.
4. Prepare a simple test sheet with these labels:

```text
drone
person
car
clutter
bird
```

5. Prepare measurement points if the site allows it:

```text
30 m
50 m
80 m
100 m
```

6. Prepare one phone video angle that records the target and test distance as
human evidence.

## Preflight Commands

From the project root:

```powershell
git status --short --branch
pio run
```

Start or confirm NodeA bridge:

```powershell
$nodeBridge = Get-ChildItem tools -Filter "node_a_serial_bridge_*.py" | Select-Object -First 1
python $nodeBridge.FullName --port COM4 --baud 115200 --output-file captures/e2e_node_status.json --echo
```

Start the Dashboard:

```powershell
$web = Get-ChildItem tools -Filter "vision_web_server_*.py" | Select-Object -First 1
python $web.FullName --host 127.0.0.1 --port 8765
```

Start the real camera bridge. Use `source=1` if that is still the correct
camera:

```powershell
$vision = Get-ChildItem tools -Filter "vision_bridge_*.py" | Select-Object -First 1
python $vision.FullName --source 1 --backend dshow --tracker csrt --width 1280 --height 720 --status-file captures/latest_status.json
```

Open:

```text
http://127.0.0.1:8765
```

## Day-Of Collection Commands

Record drone:

```powershell
python tools/collect_drone_dataset.py --label drone --duration-s 60 --interval-ms 200 --active-only --output datasets/drone_recognition/real_tracks.csv
```

Record person:

```powershell
python tools/collect_drone_dataset.py --label person --duration-s 60 --interval-ms 200 --active-only --output datasets/drone_recognition/real_tracks.csv
```

Record car:

```powershell
python tools/collect_drone_dataset.py --label car --duration-s 60 --interval-ms 200 --active-only --output datasets/drone_recognition/real_tracks.csv
```

Record clutter:

```powershell
python tools/collect_drone_dataset.py --label clutter --duration-s 60 --interval-ms 200 --output datasets/drone_recognition/real_tracks.csv
```

## Validation Command

Use PowerShell to avoid terminal encoding problems with the classifier script
filename:

```powershell
$clf = Get-ChildItem tools -Filter "multirotor_classifier_*.py" | Select-Object -First 1
python $clf.FullName --input datasets/drone_recognition/real_tracks.csv --output-dir outputs/drone_recognition_real --min-accuracy 0.80 --min-recall 0.80
```

Expected output files:

```text
outputs/drone_recognition_real/multirotor_classifier_summary.json
outputs/drone_recognition_real/multirotor_classifier_summary.csv
outputs/drone_recognition_real/multirotor_features.png
outputs/drone_recognition_real/multirotor_confusion_matrix.png
```

## Evidence To Save

For every field session, save:

```text
label
distance
weather
lighting
target description
NodeA/NodeB wiring state
camera source index
CSV output path
Dashboard screenshot
phone reference video filename
```

## Pass Criteria

For the first real-data pass, the goal is not perfection. The minimum useful
result is:

- CSV is generated with real rows
- each session has the correct label
- classifier summary is generated
- confusion matrix is generated
- failures are reported honestly

Only claim measured recognition performance after the real dataset contains at
least one positive label and one negative label.
