# 2026-06-10 Vision Drone YOLO Model Card V1

This model card records the Flytotal V1/V2 PC-side drone visual confirmation
model. It is not an ESP32 firmware change and does not modify the radar
multirotor classifier.

## Model

- Model name: `drone-yolov8n`
- Base architecture: YOLOv8n detection
- Runtime path: PC vision bridge ONNX sidecar
- Export target: `models/yolov8n_drone.onnx`
- Class list: `0: drone`
- Training run: `runs/drone/v1_w2`
- Training weights: `runs/drone/v1_w2/weights/best.pt`
- Exported ONNX SHA256: `fae760436377ce66713be5cd5717cb945960c9f5878296923219af05a0a5ff45`
- ONNX input: `images`, shape `[1, 3, 640, 640]`
- ONNX output: `output0`, shape `[1, 5, 8400]`

## Dataset

The V1/V2 training set combines two licensed Roboflow Universe datasets plus
local empty-label background images from Flytotal captures.

| Source | License | Classes Used | Images | Notes |
|--------|---------|--------------|--------|-------|
| [drones detection with yolov8](https://universe.roboflow.com/zhejiang-university-china-dliq1/drones-detection-with-yolov8) | Public Domain | source class `1: drone` | 4,231 raw images | Source also contains class `0`, which was not mapped to drone. |
| [YOLOv8_DetFly(02)](https://universe.roboflow.com/yolov8-drone-detection/yolov8_detfly-02) | CC BY 4.0 | source class `0: UAV` mapped to `drone` | 6,913 raw images | Single UAV class, normalized to project class `0: drone`. |
| `captures/*` | local project evidence | empty-label background | 36 raw images | Negative/background samples from Flytotal scenes. |

Do not train the official demo model on data with unclear license.

Prepared dataset summary from `datasets/drone_recognition/dataset_summary.json`:

| Split | Images | Positive Images | Background Images | Boxes |
|-------|--------|-----------------|-------------------|-------|
| train | 7,838 | 5,797 | 2,041 | 5,879 |
| val | 2,218 | 1,655 | 563 | 1,683 |
| test | 1,124 | 828 | 296 | 847 |
| total | 11,180 | 8,280 | 2,900 | 8,409 |

Dataset preparation command:

```powershell
.\.venv-vision\Scripts\python.exe tools\prepare_drone_yolo_dataset.py --source datasets\drone_recognition\raw\drones_detection_yolov8 --source datasets\drone_recognition\raw\yolov8_detfly_02 --source-class-ids datasets\drone_recognition\raw\drones_detection_yolov8=1 --source-class-ids datasets\drone_recognition\raw\yolov8_detfly_02=0 --include-captures --clear
```

AOD4 is not part of this main V1/V2 training set. It remains a candidate for
future bird, airplane, and helicopter false-positive checks.

## Training Command

```powershell
.\.venv-vision\Scripts\yolo.exe detect train data=datasets\drone_recognition\drone.yaml model=yolov8n.pt epochs=100 imgsz=640 batch=16 device=0 project=C:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal\runs\drone name=v1_w2 workers=2 plots=False max_det=50
```

The run was resumed once from:

```powershell
.\.venv-vision\Scripts\yolo.exe detect train model=runs\drone\v1_w2\weights\last.pt resume=True
```

Training completed with exit code `0`. `best.pt` and `last.pt` both exist under
`runs/drone/v1_w2/weights/`.

## Export Command

```powershell
.\.venv-vision\Scripts\python.exe tools\export_yolo_models.py --weights runs\drone\v1_w2\weights\best.pt --output models\yolov8n_drone.onnx --model-label drone
.\.venv-vision\Scripts\python.exe tools\check_vision_models.py --model models\yolov8n_drone.onnx
Get-FileHash models\yolov8n_drone.onnx -Algorithm SHA256
```

`check_vision_models.py` result:

```text
ok=1 model=models/yolov8n_drone.onnx hint=drone_specific_candidate
sha256=fae760436377ce66713be5cd5717cb945960c9f5878296923219af05a0a5ff45
input name=images shape=[1, 3, 640, 640] type=tensor(float)
output name=output0 shape=[1, 5, 8400] type=tensor(float)
```

Do not commit `.pt`, `.onnx`, image data, labels, or `runs/`.

## Metrics

Final epoch metrics from `runs/drone/v1_w2/results.csv`:

| Metric | Value |
|--------|-------|
| Epoch | 100 |
| Precision | 0.93115 |
| Recall | 0.80808 |
| mAP50 | 0.85030 |
| mAP50-95 | 0.48616 |
| Validation images | 2,218 |
| Validation boxes | 1,683 |
| Test images prepared | 1,124 |
| False positives observed | Not yet measured on held-out field video/AOD4 confusion set |

Best checkpoint notes:

| Selection | Epoch | Precision | Recall | mAP50 | mAP50-95 |
|-----------|-------|-----------|--------|-------|----------|
| Best by mAP50-95 | 97 | 0.92992 | 0.80986 | 0.85064 | 0.48682 |
| Best by mAP50 | 90 | 0.93751 | 0.81120 | 0.85823 | 0.48527 |

The exported ONNX uses `best.pt`, not `last.pt`.

## Vision Bridge Command

```powershell
.\.venv-vision\Scripts\python.exe tools\vision_bridge_视觉桥接.py --yolo-enabled --yolo-model models\yolov8n_drone.onnx --yolo-class-ids 0 --yolo-class-names 0:drone --yolo-model-label drone-yolov8n
```

Expected state:

```text
detector_state=READY_ONNX
class_name=drone
```

## Honest Boundary

This model is a lightweight PC-side visual confirmation model trained from
licensed image datasets and 36 local background captures. It is not proof of
stable 100 m drone identification by itself. The correct project claim is:

```text
LD2451/LD2450 provide motion and track cues; the PC vision model provides
drone-like visual confirmation when the target is visible and sufficiently
resolved.
```

V3 will add DF200 field data after manual YOLOv8 annotation. The first V3 target
distances are 10 m, 30 m, and 50 m. The 80 m and 100 m captures are challenge
validation data only and must not be described as stable-recognition evidence
without field test proof.

## 2026-07-13 V4b Audit and Promotion

The former V1 model had an incorrect source mapping: source classes `0` and `1`
in `drones_detection_yolov8` both contain drone images, while V1 mapped only
class `1`. V4b corrects this mapping and adds 800 training backgrounds,
including 968 mined COCO train2017 hard negatives. V4b was promoted after the
audit below and is now the deployed model.

Candidate artifact:

- ONNX: `models/yolov8n_drone_v4b_candidate.onnx`
- SHA256: `c33aba9e6e24ce24ae6147a538b46b0c1080093242f0ad1c59100c738121ac74`
- Weights: `runs/drone/v4b_hardneg_head_ft12/weights/best.pt`
- Dataset: `datasets/drone_recognition/v4b_hardneg`
- Dataset size: 12,279 images and 11,750 drone boxes
- ONNX input/output: `[1,3,640,640]` / `[1,5,8400]`

Independent V3 test split at confidence `0.45`:

| Runtime | Precision | Recall | F1 | TP | FP | FN |
|---------|-----------|--------|----|----|----|----|
| PyTorch GPU | 0.95506 | 0.77982 | 0.85859 | 85 | 4 | 24 |
| Ultralytics ONNX CPU | 0.95506 | 0.77982 | 0.85859 | 85 | 4 | 24 |
| Sidecar CPU after letterbox fix | 0.95506 | 0.77982 | 0.85859 | 85 | 4 | 24 |

The original Sidecar used direct `640x640` stretching and reached only
`R=0.67890` on the same 103 images. The production code now uses standard
letterbox preprocessing with pad value 114 and reverses the scale and padding
when decoding boxes. This restored 11 true positives without adding false
positives.

Negative and runtime evidence:

- Full COCO val2017: 120 triggers in 5,000 images at confidence `0.45`.
- Stratified COCO runtime sample: 17 triggers in 333 images.
- Local captures: 0 triggers in 39 images.
- CPU latency over 475 images: mean 30.555 ms, P95 34.816 ms with 8 ONNX intra-op threads.
- Model-promotion vision regression: `PASS (11/11)`; the current integrated
  PC-tool regression after field-data, startup-command, strict CLI/API closure, and stale-event guards is `PASS (20/20)`.

Promotion was explicitly approved on 2026-07-13. The V4b artifact now occupies
`models/yolov8n_drone.onnx`; the exact V1 deployment is retained at
`models/yolov8n_drone_v1_backup_2026-07-13.onnx` with SHA256
`fae760436377ce66713be5cd5717cb945960c9f5878296923219af05a0a5ff45`.
Field distance tests and the real COM4 same-event `15/15` evidence remain open.

Sustained latency note: default ONNX Runtime threading oversubscribed this
machine's 24 logical CPUs together with OpenCV. Two default-thread 475-image
runs failed with P95 latency above 570 ms. The deployed bridge now uses 8
intra-op threads, 1 inter-op thread, and sequential execution. The final full
code-path run passed at 34.816 ms P95 without changing detection metrics.
