# Drone Recognition Offline Dataset

This folder is the lightweight starting point for phase 1: offline drone / non-drone recognition testing.

The goal is not to claim 100 m live drone recognition yet. The goal is to build measurable evidence first:

- drone / UAV / multirotor tracks should be classified as positive
- people, birds, vehicles, and static clutter should be classified as negative
- every run should produce a JSON summary, CSV features, a feature plot, and a confusion matrix

## Files

- `sample_tracks.csv`: small labeled example that matches the current classifier input format.
- `raw/`: optional local-only folder for videos, images, screenshots, or exported radar logs. Keep large raw assets out of Git.

## CSV Format

Required fields:

```text
timestamp_ms,track_id,x_mm,y_mm,vx_mm_s,vy_mm_s,label
```

Positive labels recognized by the current script include:

```text
drone,uav,multirotor,hover
```

Use negative labels for distractors, for example:

```text
person,bird,car,ebike,tree,clutter
```

## Run

From the project root:

```powershell
$clf = Get-ChildItem tools -Filter "multirotor_classifier_*.py" | Select-Object -First 1
python $clf.FullName --input datasets/drone_recognition/sample_tracks.csv --output-dir outputs/drone_recognition --min-accuracy 0.80 --min-recall 0.80
```

Expected local outputs:

- `outputs/drone_recognition/multirotor_classifier_summary.json`
- `outputs/drone_recognition/multirotor_classifier_summary.csv`
- `outputs/drone_recognition/multirotor_features.png`
- `outputs/drone_recognition/multirotor_confusion_matrix.png`

When you replace `sample_tracks.csv` with real collected data, keep the same columns and labels. If the real-data score fails, report the failure as a dataset finding instead of hiding it; that is stronger evidence than a polished but fake result.

## Collect Real Track Data

Keep NodeA bridge, NodeB, the vision bridge, and the Dashboard running. Then
record one labeled session at a time.

Drone example:

```powershell
python tools/collect_drone_dataset.py --label drone --duration-s 60 --interval-ms 200 --active-only --output datasets/drone_recognition/real_tracks.csv
```

Person example:

```powershell
python tools/collect_drone_dataset.py --label person --duration-s 60 --interval-ms 200 --active-only --output datasets/drone_recognition/real_tracks.csv
```

Car example:

```powershell
python tools/collect_drone_dataset.py --label car --duration-s 60 --interval-ms 200 --active-only --output datasets/drone_recognition/real_tracks.csv
```

Clutter example:

```powershell
python tools/collect_drone_dataset.py --label clutter --duration-s 60 --interval-ms 200 --output datasets/drone_recognition/real_tracks.csv
```

After collecting several sessions, run:

```powershell
$clf = Get-ChildItem tools -Filter "multirotor_classifier_*.py" | Select-Object -First 1
python $clf.FullName --input datasets/drone_recognition/real_tracks.csv --output-dir outputs/drone_recognition_real --min-accuracy 0.80 --min-recall 0.80
```
