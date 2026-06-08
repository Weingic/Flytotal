# 2026-06-08 Real Data Collection SOP V1

本 SOP 属于 2026-06-08「视觉模型 + 多旋翼真分类器 + 真数据 SOP」计划的 D 路。目标是让真实无人机、行人、车辆、杂波等轨迹能按同一 CSV 格式采集，并直接喂给 `tools/multirotor_classifier_验证.py --train`。

## 先看红线

采集前必须先确认雷达航迹链有效：

```text
track_active=1
track_confirmed=1
x_mm/y_mm/vx_mm_s/vy_mm_s 有真实变化
```

如果 `main_state` 长时间恒 `IDLE`，或者 `track_active=0`、`track_confirmed=0`，先修 LD2450/航迹确认链，再采数据。否则 CSV 只是空轨迹或假轨迹，训练结果没有意义。

## 采集目标

每类至少采 20 条 track。最低可用目标如下：

```text
drone   真多旋翼无人机，正样本
person  行人，负样本
ebike   电动车/自行车，负样本
car     汽车，负样本
bird    鸟，如果现场能安全采到，负样本
clutter 静止杂波/环境扰动，负样本
```

正样本标签只使用：

```text
drone,uav,multirotor,hover
```

建议现场统一用 `drone`，避免后期混乱。

## CSV 格式

输出文件固定为：

```text
datasets/drone_recognition/real_tracks.csv
```

列名必须严格一致：

```text
timestamp_ms,track_id,x_mm,y_mm,vx_mm_s,vy_mm_s,label
```

每条 track 至少 5 个时间点。采集命令默认 `--interval-ms 200`，所以每条 track 至少稳定 1 秒以上，最好 8 到 12 秒。

## 硬件与软件启动

硬件连接：

```text
NodeA ESP32-S3 -> PC USB，通常 COM4
NodeB ESP32-C3 -> PC USB，通常 COM6
NodeB UART TX/RX/GND -> NodeA 身份链串口
LD2450 -> NodeA 近距轨迹输入
LD2451 -> NodeA 远距运动预警输入
UVC 摄像头 -> PC USB
```

终端 1：启动 NodeA 串口桥接。

```powershell
$bridge = Get-ChildItem tools -Filter "node_a_serial_bridge_*.py" | Select-Object -First 1
python $bridge.FullName --port COM4 --baud 115200 --output-file captures/e2e_node_status.json --events-file captures/e2e_node_events.json --event-store-file captures/e2e_node_event_store.json --startup-command MONITOR,CLEAN --startup-command REALINPUT,ON --startup-command TESTMODE,OFF --startup-command SERVO,ON
```

终端 2：启动视觉桥。先用通用模型或不加 YOLO 都可以，采雷达轨迹时关键是 NodeA status JSON。

```powershell
$vision = Get-ChildItem tools -Filter "vision_bridge_*.py" | Select-Object -First 1
python $vision.FullName --source 0 --backend dshow --tracker csrt --width 1280 --height 720 --status-file captures/latest_status.json
```

如果已经导出通用 YOLO：

```powershell
python $vision.FullName --source 0 --backend dshow --tracker csrt --width 1280 --height 720 --status-file captures/latest_status.json --yolo-enabled --yolo-model models/yolov8n.onnx --yolo-class-ids 4,14 --yolo-class-names 4:airplane,14:bird --yolo-model-label coco-yolov8n
```

终端 3：启动 Dashboard。

```powershell
$web = Get-ChildItem tools -Filter "vision_web_server_*.py" | Select-Object -First 1
python $web.FullName --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

## 现场检查

采任何数据前，先让一个人在 LD2450 前方 1.5 到 3 米慢走，确认 Dashboard 或 `captures/e2e_node_status.json` 里能看到：

```text
track_active=1
track_confirmed=1
x_mm/y_mm 有变化
vx_mm_s/vy_mm_s 有变化
```

如果看不到，停止采集，排查：

```text
LD2450 供电
LD2450 朝向
LD2450 串口接线
REALINPUT,ON 是否生效
TESTMODE,OFF 是否生效
雷达前方是否太近、太远、遮挡太多
```

## 距离与动作

每类目标覆盖三个距离点：

```text
10 m  NEAR
30 m  MID
50 m  FAR
```

每个距离点每类至少 5 条 track。

无人机动作建议：

```text
hover     悬停 8 到 12 秒
approach  从远到近慢速接近
depart    从近到远离开
cross     横向飞过雷达视野
```

负样本动作建议：

```text
person  行人左右慢走、接近、远离
ebike   慢速横穿
car     安全距离内低速经过
bird    只能自然观察，不能人为驱赶
clutter 无目标，记录环境反射和静态扰动
```

## 采集命令

每次只采一个标签、一个距离、一个动作。用 `--session-id` 把现场记录写进 track_id，后期不容易混。

无人机 10m 悬停：

```powershell
python tools/collect_drone_dataset.py --label drone --duration-s 12 --interval-ms 200 --active-only --session-id drone_10m_hover_01 --output datasets/drone_recognition/real_tracks.csv
```

无人机 30m 横飞：

```powershell
python tools/collect_drone_dataset.py --label drone --duration-s 12 --interval-ms 200 --active-only --session-id drone_30m_cross_01 --output datasets/drone_recognition/real_tracks.csv
```

行人 10m 横穿：

```powershell
python tools/collect_drone_dataset.py --label person --duration-s 12 --interval-ms 200 --active-only --session-id person_10m_cross_01 --output datasets/drone_recognition/real_tracks.csv
```

电动车 30m 横穿：

```powershell
python tools/collect_drone_dataset.py --label ebike --duration-s 12 --interval-ms 200 --active-only --session-id ebike_30m_cross_01 --output datasets/drone_recognition/real_tracks.csv
```

汽车 50m 低速经过：

```powershell
python tools/collect_drone_dataset.py --label car --duration-s 12 --interval-ms 200 --active-only --session-id car_50m_pass_01 --output datasets/drone_recognition/real_tracks.csv
```

杂波：

```powershell
python tools/collect_drone_dataset.py --label clutter --duration-s 20 --interval-ms 200 --session-id clutter_site_idle_01 --output datasets/drone_recognition/real_tracks.csv
```

如果 `--active-only` 导致 `rows=0`，说明没有稳定 track。不要强行去掉参数伪造数据，先回到“现场检查”排查。

## 现场记录表

每采一条，在纸上或手机里记录：

```text
session_id
label
距离
动作
天气/风
是否有遮挡
是否有强反射物
是否 track_confirmed=1
备注
```

示例：

```text
drone_30m_cross_01, drone, 30m, 横飞, 微风, 无遮挡, 附近有铁栏杆, confirmed=1, 画面清晰
```

## 训练验证

采完后先跑格式和训练管线：

```powershell
python tools/multirotor_classifier_验证.py --input datasets/drone_recognition/real_tracks.csv --train --output-dir outputs/drone_recognition_real
```

期望输出：

```text
outputs/drone_recognition_real/multirotor_classifier_summary.json
outputs/drone_recognition_real/multirotor_classifier_summary.csv
outputs/drone_recognition_real/multirotor_tree.png
outputs/drone_recognition_real/multirotor_tree_rules.txt
outputs/drone_recognition_real/multirotor_roc_real.png
outputs/drone_recognition_real/multirotor_confusion_real.png
outputs/drone_recognition_real/multirotor_rule_vs_model.png
models/multirotor_tree.pkl
```

如果准确率或召回率不达标，不要硬改标签。把它记录为真实数据发现，再分析是雷达轨迹质量、样本量、环境反射还是动作覆盖不够。

## RID 说明

真无人机的真实 Remote ID 不一定能被当前 NodeB 扫到。当前 Demo 的合作目标仍用 NodeB 模拟身份链证明：

```text
合作目标：RID / 白名单通过，系统压低风险
非合作目标：无白名单或身份异常，系统进入风险闭环
```

真实无人机采集主要用于“运动轨迹 + 视觉确认 + 多旋翼分类器”链路，不把它和真实 RID 识别混在一起承诺。

## 常见坑

1. 雷达没确认目标就开始采，最后 CSV 没有效轨迹。
2. 人或无人机离 LD2450 太近，轨迹容易乱跳。
3. 室内金属物、玻璃、桌腿会造成反射。
4. 风大时无人机姿态和速度变化大，先采低风样本。
5. 只采无人机，不采负样本，分类器无法证明“区分能力”。
6. 只看总准确率，不看 `drone` 召回率和误报。
7. 通用 COCO YOLO 没有 `drone` 类，不能说已经视觉识别无人机。
