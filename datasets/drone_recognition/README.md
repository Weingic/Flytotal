# Drone Recognition Dataset

## 2026-07-13 当前入口

详细现场流程统一使用：

[`docs/2026-06-08_real_data_collection_sop_v1.md`](../../docs/2026-06-08_real_data_collection_sop_v1.md)

本目录只说明数据格式和最短命令，不再维护第二套现场 SOP。

## 文件

- `sample_tracks.csv`：带标签的小型格式与算法样例，不是真实外场指标。
- `real_tracks.csv`：当前活动真实数据集。2026-07-13 已建立干净 7 列基线，现场数据量暂为 0。
- `raw/`：本地原始视频、截图、雷达日志和旧数据归档，不提交到 Git。
- `raw/archive/2026-05-16_unverified_clutter_tracks.csv`：门禁升级前的 50 行全零 clutter 记录，仅供追溯，不进入当前正式指标。

## CSV 格式

列名必须严格为：

```text
timestamp_ms,track_id,x_mm,y_mm,vx_mm_s,vy_mm_s,label
```

正样本标签统一使用 `drone`。常用负样本标签为 `person`、`bird`、`car`、`ebike` 和 `clutter`。

## 先验证样例流程

```powershell
python tools\multirotor_classifier_验证.py --input datasets\drone_recognition\sample_tracks.csv --output-dir outputs\drone_recognition --min-accuracy 0.80 --min-recall 0.80
```

该结果只证明分类管线和格式正常，不能作为真实无人机性能。

## 采一段真实轨迹

只有 NodeA 同时满足 `online=1`、`track_active=1`、`track_confirmed=1` 且运动字段真实变化时，才运行：

```powershell
python tools\collect_drone_dataset.py --label drone --duration-s 12 --interval-ms 200 --active-only --session-id drone_near_measured_hover_01
```

每段必须使用新 `session-id`。如果重复，采集器会在写入前返回 `SESSION_ID_EXISTS`；不要在正式数据中使用 `--allow-session-reuse` 或 `--allow-stale`。

## 记录一次视觉/远距外场试验

`real_tracks.csv` 只保存 LD2450 二维轨迹。10/30/50米视觉与 LD2451 试验使用只读记录器，不得伪装成二维轨迹：

```powershell
python tools\field_trial_recorder.py --session-id drone_10m_hover_01 --target drone --distance-m 10 --distance-source laser --action hover --site field_a --weather clear --lighting daylight --video-ref phone_drone_10m_hover_01 --duration-s 12
```

每次会话的逐点状态和摘要写入 `captures/session_logs/field_trials/<session_id>/`。正式统计只接受 `trial_valid=true`、视频已形成 SHA256 且 `evidence_complete=true` 的报告；是否识别正确单独读取 `performance_pass` 和 `outcome`，不能把“记录成功”写成“识别成功”。完整参数和视频补哈希命令见现场 SOP。

出发前先通过统一收件箱开启增强融合，再运行 `python tools\field_collection_preflight.py --mode distance`。必须为物理摄像头 source、`fusion_enabled=1` 并达到 `GO 17/17`；视频文件回放固定 `NO-GO`，只能用于集成回归。完整同事件任务使用 `--mode same-event`，要求 `GO 18/18`。

核心距离矩阵要求 `drone/person/car x 10/30/50 m x 3`，另加两段 20 分钟长稳。采集过程中随时运行：

```powershell
python tools\field_evidence_gate.py
```

当前尚无真实外场报告，因此正确基线是 `NO-GO 3/22`、距离剩余 27 次、长稳剩余 2 次。只有独立视频完成哈希、正式 V4b 哈希绑定、全部报告可读并最终达到 `GO 22/22`，才算采集证据齐全。

## 验收真实数据

```powershell
python tools\multirotor_classifier_验证.py --input datasets\drone_recognition\real_tracks.csv --train --output-dir outputs\drone_recognition_real --min-accuracy 0.80 --min-recall 0.80
```

真实文件为空时，工具必须返回 `ERROR,no_real_tracks`、`ok=false` 和非零退出，不会自动换成合成数据。只有明确执行下面的命令才会运行 12 条合成算法基线：

```powershell
python tools\multirotor_classifier_验证.py --mock --output-dir outputs\drone_recognition_mock
```

`--mock` 结果必须标为 synthetic，不得写入真实外场指标或国赛主证据。
