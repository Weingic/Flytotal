# 2026-07-09 NodeA 功能更新

## 计划位置

2026-07-09 / 国一冲刺 / 视觉演示稳定性修复

## 今日目标

把 2026-07-08 证据采集时暴露出来的视觉桥接启动风险收掉。昨天为了拿到带图像的事件证据，临时用运行时补丁启用了 `MIL` tracker；今天把这个能力正式接入工具，避免国一录屏或现场演示时再因为 `CSRT/KCF` 不可用而启动失败。

## 改动内容

1. `tools/vision_bridge_视觉桥接.py`
   - `SUPPORTED_TRACKERS` 从 `csrt/kcf` 扩展为 `csrt/kcf/mil`。
   - `tracker_available()` 增加 `TrackerMIL_create` 检测。
   - `create_tracker()` 增加 `MIL` tracker 创建路径。
   - 默认优先级仍是 `csrt -> kcf -> mil`，有更强 tracker 的环境不会被降级；当前机器没有 `CSRT/KCF` 时会自动 fallback 到 `MIL`。

2. `tools/usb_camera_readiness_check_USB摄像头就绪核对.py`
   - 摄像头预检同样支持 `MIL` tracker。
   - 推荐命令不再写死 `csrt/kcf`，而是按 `SUPPORTED_TRACKERS` 顺序选择当前可用 tracker。
   - 当前机器推荐命令为：

```powershell
python tools\vision_bridge_视觉桥接.py --backend dshow --source 0 --tracker mil --tracker-fallback auto --source-warmup-frames 12
```

## 验收结果

Tracker 列表：

```powershell
python tools\vision_bridge_视觉桥接.py --list-trackers
```

结果：

```text
Available trackers: MIL
```

摄像头预检：

```powershell
python tools\usb_camera_readiness_check_USB摄像头就绪核对.py --backend dshow --start-index 0 --end-index 1 --warmup-frames 3 --recommended-tracker-fallback auto
```

关键结果：

```text
result=PASS
camera_ready_count=1
trackers_available=MIL
recommended_tracker=mil
recommended_command=python tools/vision_bridge_视觉桥接.py --backend dshow --source 0 --tracker mil --tracker-fallback auto --source-warmup-frames 12
```

语法检查：

```powershell
python -m py_compile "tools\vision_bridge_视觉桥接.py" "tools\usb_camera_readiness_check_USB摄像头就绪核对.py"
```

结果：通过。

## 解决的问题

之前当前 Python 环境里 `cv2` 有 `TrackerMIL_create`，但没有 `TrackerCSRT_create` 和 `TrackerKCF_create`。旧工具只允许 `csrt/kcf`，所以会显示：

```text
Available trackers: NONE
```

这会导致视觉桥接无法正常启动。现在工具能识别 `MIL`，摄像头预检也能给出可直接使用的启动命令，录屏前不需要再手动写运行时补丁。

## 下一步

1. 用推荐命令启动视觉桥接。
2. 保持网页服务运行在 `http://127.0.0.1:8765/vision_dashboard.html`。
3. 用 COM4 串口桥接触发真实事件。
4. 录一段完整视频，覆盖：视觉锁定、事件打开、云端命令、网页事件详情、证据 JSON 导出。
