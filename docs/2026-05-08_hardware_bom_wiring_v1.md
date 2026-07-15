# Flytotal v5.2 硬件 BOM 与接线表

本文档是 Flytotal v5.2 的正式硬件连接表，面向现场接线、排障、答辩说明三种用途。当前硬件口径是：

```text
NodeA ESP32-S3 主感知节点
NodeB ESP32-C3 身份链/协同节点
LD2450 近距毫米波雷达
LD2451 远距运动触发雷达
USB 摄像头接 PC
Pan/Tilt 云台舵机由 NodeA 输出 PWM
```

注意：当前 `NodeA + NodeB` 不是两套完整 A1/A2 感知节点。NodeB 当前是辅助身份链节点，通过 UART 把心跳、RID、白名单状态发给 NodeA。

## 1. 物料清单

| 模块 | 建议型号 | 数量 | 供电 | 估算电流 | 项目作用 |
| --- | --- | ---: | --- | ---: | --- |
| NodeA 主控 | ESP32-S3 DevKitC / ESP32-S3 N8 | 1 | USB 5V，IO 3.3V | 150-300mA | 主感知、融合、云台控制、串口输出、云端 AI |
| NodeB 身份链节点 | ESP32-C3 SuperMini | 1 | USB 5V，IO 3.3V | 80-180mA | RID/白名单/协同状态上报 |
| 近距雷达 | LD2450 | 1 | 以模块规格为准，常见 5V | 约 100mA | 近距轨迹、人体/目标跟踪、云台粗跟随 |
| 远距雷达 | LD2451 | 1 | 以模块规格为准，常见 5V | 约 100-200mA | 10-100m 级远距运动预警 |
| USB 摄像头 | UVC 工业摄像头 / USB 摄像头 | 1 | PC USB | 100-500mA | PC 侧视觉锁定、YOLO/CSRT、抓拍证据 |
| Pan 舵机 | SG90/MG90S 或同类 | 1 | 独立 5V 推荐 | 峰值可达数百 mA | 云台水平转动 |
| Tilt 舵机 | SG90/MG90S 或同类 | 1 | 独立 5V 推荐 | 峰值可达数百 mA | 云台俯仰转动 |
| USB 转 TTL | CH340/CP2102 | 0-1 | PC USB | - | LD2451 单测、串口排障 |
| 外部电源 | 5V/2A 以上或 DC-DC 降压 | 0-1 | 5V | 视负载 | 舵机/外场稳定供电 |
| 杜邦线/面包板/共地线 | 常规 | 若干 | - | - | 硬件连接 |

## 2. 总体供电原则

| 组合 | 建议供电 | 说明 |
| --- | --- | --- |
| NodeA 单板 | PC USB | 只做烧录、串口命令、无舵机大动作时可用 |
| NodeA + LD2450 + LD2451 | 稳定 5V/1A 以上 | 雷达和 NodeA 必须共 GND |
| NodeA + 云台舵机 | 舵机独立 5V/2A，NodeA USB 供电 | 舵机电源 GND 必须接 NodeA GND |
| NodeA + NodeB | 两块板可各自 USB 供电 | 两块板 GND 必须相连 |
| 完整演示 | NodeA/NodeB 各自 USB，舵机独立 5V，摄像头接 PC | 避免让 ESP32 USB 口直接带舵机 |

常见“算法像坏了”的问题其实是供电问题：

- 舵机抖动或乱转：优先查舵机独立 5V 和共地。
- 雷达数据断断续续：优先查模块供电和 GND。
- 串口乱码：优先查波特率、TX/RX 是否交叉、是否共地。
- NodeA 重启：优先查 USB 供电能力、舵机是否从 NodeA 取电。

## 3. NodeA ESP32-S3 引脚总表

以 `include/AppConfig.h` 为准，当前固件配置如下。

| 功能 | NodeA 引脚 | 连接对象 | 波特率/参数 | 必接 | 说明 |
| --- | --- | --- | --- | --- | --- |
| USB 串口 | USB | PC | 115200 | 是 | 烧录、监视器、命令输入，常见端口 `COM4` |
| LD2450 RX | GPIO18 | LD2450 TX | 256000 | 是 | NodeA 接收 LD2450 轨迹数据 |
| LD2450 TX | GPIO17 | LD2450 RX | 256000 | 可选 | 只读雷达时可先不接 |
| LD2451 RX | GPIO13 | LD2451 TX | 115200 | 是 | NodeA 接收 LD2451 远距触发数据，固件已启用 RX pullup |
| LD2451 TX | GPIO14 | LD2451 RX | 115200 | 可选 | 当前建议先不接，等只读链稳定后再接 |
| NodeB RX | GPIO15 | NodeB GPIO4 TX | 115200 | 是 | NodeA 接收 NodeB 心跳和 RID |
| NodeB TX | GPIO16 | NodeB GPIO5 RX | 115200 | 可选 | 后续双向控制预留；第一轮可不接 |
| Pan PWM | GPIO4 | Pan 舵机信号线 | 50Hz | 可选 | 水平舵机信号，舵机电源独立 |
| Tilt PWM | GPIO5 | Tilt 舵机信号线 | 50Hz | 可选 | 俯仰舵机信号，和 Pan 共地 |
| GND | GND | 所有外设 GND | - | 是 | 所有串口设备、雷达、舵机电源必须共地 |

## 4. LD2450 近距雷达接线

LD2450 是近距轨迹主链，影响 `track_active`、`track_confirmed`、云台跟随和事件风险。

| LD2450 引脚 | 接到 NodeA | 必接 | 说明 |
| --- | --- | --- | --- |
| TX | GPIO18 RX | 是 | 雷达发数据，NodeA 收数据 |
| RX | GPIO17 TX | 可选 | 只读测试可不接 |
| GND | GND | 是 | 必须和 NodeA 共地 |
| VCC | 模块要求电源 | 是 | 按模块规格供电，常见 5V |

检查方式：

```text
REALINPUT,ON
TESTMODE,OFF
SERVO,ON
STATUS
```

期望看到：

```text
track_active=1
track_confirmed=1
x/y/vx/vy 有变化
```

如果一直 `track_active=0`，先查 LD2450 供电、朝向、TX/RX、波特率和前方是否有有效运动目标。

## 5. LD2451 远距雷达接线

LD2451 当前定位是远距运动预警，不是无人机专用识别雷达。它负责 `far_motion_trigger`、`fusion_stage=FAR`、`target_verdict=MOTION_ALERT` 等远距提示。

| LD2451 引脚 | 接到 NodeA | 必接 | 说明 |
| --- | --- | --- | --- |
| TX | GPIO13 RX | 是 | 推荐第一阶段只接这根数据线 |
| RX | GPIO14 TX | 可选 | 先不接；之前接上后如果有响声/异常，保持只读 |
| GND | GND | 是 | 必须和 NodeA 共地 |
| VCC | 模块要求电源 | 是 | 按模块规格供电 |

固件参数：

```text
Ld2451BaudRate=115200
Ld2451RxPin=13
Ld2451TxPin=14
Ld2451RxPullupEnabled=true
Ld2451TaskStackSize=12288
```

检查命令：

```text
LD2451,SELFTEST
FUSION,ENABLE,1
LD2451,range_m=50,speed_mps=1.2,approach=1,valid=1
FUSION,STATUS
```

期望看到：

```text
ld2451_valid=1
far_motion_trigger=1
fusion_stage=FAR
target_verdict=MOTION_ALERT
```

## 6. NodeB ESP32-C3 身份链接线

NodeB 运行 `examples/nodeb_c3_identity_uart` 示例工程。它不是第二套完整雷达节点，而是身份链/协同上报节点。

| NodeB C3 引脚 | 接到 NodeA | 必接 | 说明 |
| --- | --- | --- | --- |
| GPIO4 TX | NodeA GPIO15 RX | 是 | NodeB 发心跳/RID，NodeA 收 |
| GPIO5 RX | NodeA GPIO16 TX | 可选 | 预留双向通信，第一轮可不接 |
| GND | NodeA GND | 是 | 必须共地 |
| USB | PC | 建议 | NodeB 单独供电、烧录和监视，常见端口 `COM6` |

推荐供电：

```text
NodeA 和 NodeB 各自 USB 供电
只把 GND 连在一起
不要从 NodeA 信号线给 NodeB 取电
```

NodeB 默认发送：

```text
NODEB,HEARTBEAT,node=B1,source=BLE_WIFI,status=OK,rssi=-62,ble=1,wifi=1
NODEB,RID,node=B1,source=BLE,rssi=-62,status=SEEN,id=SIM-RID-001,auth_status=VALID,whitelist_tag=WL_OK
```

NodeA 期望状态：

```text
nodeb_online=1
nodeb_node_id=B1
rid_whitelist_hit=1
wl_status=WL_ALLOWED
target_verdict=CONFIRMED_COOPERATIVE_DRONE
event_active=0
```

NodeB 烧录命令：

```powershell
pio run -d examples/nodeb_c3_identity_uart
pio run -d examples/nodeb_c3_identity_uart -t upload --upload-port COM6
```

## 7. 云台舵机接线

云台只负责演示跟随和视觉粗对准。舵机供电不稳定会直接造成抖动、乱转、ESP32 重启。

| 舵机线 | 接到哪里 | 说明 |
| --- | --- | --- |
| Pan 信号线 | NodeA GPIO4 | 水平转动 |
| Tilt 信号线 | NodeA GPIO5 | 俯仰转动 |
| 舵机 VCC | 独立 5V 电源正极 | 推荐 5V/2A 或更高 |
| 舵机 GND | 独立 5V 电源负极 + NodeA GND | 必须共地 |

固件参数：

```text
PanPin=4
TiltPin=5
PwmFrequencyHz=50
PulseMinUs=500
PulseMaxUs=2500
CenterPanDeg=90
CenterTiltDeg=90
```

安全命令：

```text
SERVO,OFF
SERVO,ON
DIAG,SERVO
DIAG,STOP
TESTMODE,OFF
```

注意：

- `TESTMODE,ON` 时舵机由手动测试接管，不会自动跟随。
- 自动跟随需要 `REALINPUT,ON`、`TESTMODE,OFF`、`SERVO,ON`，并且 LD2450 要形成 `track_confirmed=1`。

## 8. USB 摄像头连接

USB 摄像头接 PC，不接 ESP32。

| 摄像头 | 接到哪里 | 说明 |
| --- | --- | --- |
| UVC USB 摄像头 | PC USB | 由 `vision_bridge_视觉桥接.py` 打开 |
| 数据链路 | PC 软件层 | 视觉结果通过串口/状态文件进入 Dashboard |
| 供电 | PC USB | 长线或高功耗摄像头建议接稳定 USB 口 |

常用启动命令：

```powershell
python tools\vision_bridge_视觉桥接.py --source 0 --backend dshow --tracker csrt --width 1280 --height 720
```

使用 COCO 通用 YOLO：

```powershell
python tools\vision_bridge_视觉桥接.py --yolo-enabled --yolo-model models\yolov8n.onnx --yolo-class-ids 4,14 --yolo-class-names 4:airplane,14:bird --yolo-model-label coco-yolov8n
```

使用无人机专用 YOLO：

```powershell
python tools\vision_bridge_视觉桥接.py --yolo-enabled --yolo-model models\yolov8n_drone.onnx --yolo-class-ids 0 --yolo-class-names 0:drone --yolo-model-label drone-yolov8n
```

## 9. 全系统 ASCII 接线图

```text
                         PC / Windows
                 +-------------------------+
                 | PlatformIO / Monitor    |
                 | Vision Bridge / Web UI   |
                 | USB Camera               |
                 +-----------+-------------+
                             |
                         USB | COM4
                             |
                    +--------v--------+
                    | NodeA ESP32-S3  |
                    | Main controller |
                    +-----------------+
       LD2450 TX ---> GPIO18 RX       GPIO17 TX ---> LD2450 RX (optional)
       LD2451 TX ---> GPIO13 RX       GPIO14 TX ---> LD2451 RX (optional)
 NodeB GPIO4 TX ---> GPIO15 RX        GPIO16 TX ---> NodeB GPIO5 RX (optional)
      Pan signal <--- GPIO4
     Tilt signal <--- GPIO5
                    |
                    | GND common
                    +------------------------------+
                                                   |
                     +-----------------------------+-------------+
                     |                                           |
              +------v------+                             +------v------+
              | NodeB C3    |                             | Servo 5V PSU |
              | COM6 / USB  |                             | Pan / Tilt   |
              +-------------+                             +-------------+
```

## 10. 推荐上电与启动顺序

1. 断电状态下检查所有 GND 是否共地。
2. 先只接 NodeA USB，确认 COM4 可用。
3. 烧录 NodeA：

```powershell
pio run -t upload --upload-port COM4
```

4. 打开 NodeA 串口：

```powershell
pio device monitor --port COM4 --baud 115200 --filter time
```

5. 发送安静模式和基础状态命令：

```text
MONITOR,CLEAN
STATUS
CONFIG,STATUS
```

6. 接 LD2450，确认近距轨迹。
7. 接 LD2451，只接 TX/GND/VCC 先测。
8. 接 NodeB，确认 `nodeb_online=1`。
9. 接舵机独立电源，确认 `SERVO,ON` 后再测试跟随。
10. 最后启动视觉桥和 Dashboard。

## 11. 现场快速自检命令

NodeA 基础：

```text
MONITOR,CLEAN
STATUS
CONFIG,STATUS
```

LD2450 / 云台：

```text
REALINPUT,ON
TESTMODE,OFF
SERVO,ON
STATUS
```

LD2451 / 融合：

```text
LD2451,SELFTEST
FUSION,ENABLE,1
LD2451,range_m=50,speed_mps=1.2,approach=1,valid=1
FUSION,STATUS
```

NodeB：

```text
NODEB,LINK
FUSION,STATUS
```

云端豆包：

```text
CLOUD,STATUS
CLOUD,TEST
```

## 12. 常见错误与排查

| 现象 | 优先检查 |
| --- | --- |
| NodeA 反复重启 | 舵机是否从 NodeA USB 取电、5V 是否压降、GND 是否松动 |
| 舵机只扫描不跟随 | `TESTMODE,OFF`、`SERVO,ON`、`REALINPUT,ON`、`track_confirmed=1` |
| LD2450 无轨迹 | TX/RX 是否交叉、波特率 256000、目标是否在有效范围、雷达朝向 |
| LD2451 无触发 | 先只接 LD2451 TX -> NodeA GPIO13 RX，确认 GND 和供电 |
| NodeB 不在线 | NodeB GPIO4 TX 是否接 NodeA GPIO15 RX、GND 是否共地、NodeB 是否在发心跳 |
| 串口乱码 | 监视器是否 115200，雷达串口不要接到 USB 监视口 |
| Dashboard 无视觉 | 摄像头是否被其他软件占用、`source` 是否正确、OpenCV 是否能打开 |
| 合作目标不生效 | NodeB RID 是否为 `SIM-RID-001`，`whitelist_tag=WL_OK` |

## 13. 答辩口径

可以这样说明硬件架构：

```text
NodeA 是主感知和融合节点，接入 LD2450 近距轨迹、LD2451 远距运动预警、云台舵机和云端 AI 链路。
NodeB 是辅助身份链节点，通过 UART 向 NodeA 上报心跳、RID 和白名单状态。
USB 摄像头运行在 PC 侧，用于视觉锁定、YOLO 检测和抓拍证据。
系统不是单一传感器识别无人机，而是远距运动预警、近距轨迹、身份链、视觉确认和云端研判的分层闭环。
```

不要夸大：

```text
LD2451 不声明为无人机专用雷达。
当前 NodeB 不声明为完整第二感知节点。
YOLO 视觉模型不单独承诺 100m 稳定识别，需要实测数据证明。
```
