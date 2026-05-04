# Flytotal v5.2 Algorithm Evidence Index

Last updated: 2026-05-03

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
python tools/gimbal_prediction_simulator.py --lead-times 0,0.12,0.18 --output-dir outputs
python tools/co_sensing_simulator.py --scenario boundary_crossing
```

## Policy

- Commit Markdown indexes and small summaries.
- Do not commit `outputs/`, raw `captures/`, videos, or `models/yolov8n.onnx`.
- If labels are missing, report `needs_labels`; do not present a fake ROC curve.

## 给小白的解释

这是什么：这是答辩证据的目录说明，不是放大文件的仓库。
有什么用：你答辩时可以按这里快速找到“融合对比图、视觉双框、筛选图、云台预测图、协同状态”。
你现在该怎么做：先跑上面的命令生成 `outputs/`，截图或录屏后，把文件路径填到答辩素材文档里。
