# Flytotal v5.2 Algorithm Evidence Index

Last updated: 2026-05-08

This directory is the lightweight index for v5.2 defense evidence. Large generated images, videos, model files, and raw captures stay outside Git by default.

## Local Evidence Paths

- `outputs/fusion_compare_<session>.png`: old three-source count vs v5.2 staged fusion.
- `outputs/multirotor_features.png`: multirotor feature distribution.
- `outputs/multirotor_confusion_matrix.png`: confusion matrix when labeled CSV data is available.
- `outputs/multirotor_needs_labels.json`: explicit reminder when history data has no labels.
- `outputs/gimbal_prediction.png`: 0 / 120 / 180 ms lead-time comparison.
- `captures/v5_2/co_sensing_boundary_crossing.json`: NodeA / NodeB handoff simulator output.
- `docs/algorithm_evidence/dashboard_dual_box_recording.mp4`: optional local recording path, not committed by default.

## Commands

```powershell
python tools/fusion_simulator.py --compare --input captures --output-dir outputs
python tools/multirotor_classifier_验证.py --input captures --output-dir outputs
python tools/multirotor_classifier_验证.py --input datasets/drone_recognition/sample_tracks.csv --output-dir outputs/drone_recognition --min-accuracy 0.80 --min-recall 0.80
python tools/gimbal_prediction_simulator.py --lead-times 0,0.12,0.18 --output-dir outputs
python tools/co_sensing_simulator.py --scenario boundary_crossing
```

## Target Verdict Levels

- `UNKNOWN_TARGET`: no reliable target judgment yet.
- `MOTION_ALERT`: far-range LD2451 motion cue only; do not claim drone recognition.
- `PROBABLE_MULTIROTOR`: confirmed near radar track plus multirotor-like motion score.
- `VISUALLY_CONFIRMED_DRONE`: visual lock is strong and backed by a radar cue.
- `CONFIRMED_COOPERATIVE_DRONE`: RID matched and whitelist gate allowed.

## Policy

- Commit Markdown indexes and small summaries.
- Do not commit `outputs/`, raw `captures/`, videos, or `models/yolov8n.onnx`.
- If labels are missing, report `needs_labels`; do not present a fake ROC curve.

## 给小白的解释

这是答辩证据目录，不是存放大视频和原始数据的地方。你先运行上面的命令生成 `outputs/`，再把关键截图、录屏路径和测试结论写进答辩素材文档。
