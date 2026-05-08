# v5.2 硬件 BOM 与接线表

## 物料清单

| 模块 | 建议数量 | 用途 | 备注 |
| --- | ---: | --- | --- |
| ESP32-S3 开发板 | 1 | NodeA 主控 | 负责 LD2450、LD2451、NodeB 串口和状态输出 |
| ESP32-C3 SuperMini | 1 | NodeB 身份链/协同节点 | 先做串口身份链，ESP-NOW 可后续扩展 |
| LD2450 | 1 | 近距毫米波雷达 | 用于近距航迹和云台角度链路 |
| LD2451 | 1 | 远距运动触发 | 只做 `far_motion_trigger`，不替代 LD2450 |
| USB 转 TTL 模块 | 1 | LD2451 单测和串口排错 | 选 `USB 转 TTL`，不是 RS485 |
| OLED 0.96 SSD1306 I2C | 可选 | 本地调试显示 | 非主链必需 |
| 有源蜂鸣器模块 | 可选 | 告警提示 | 选 3.3V/5V 兼容高电平触发款 |
| DC-DC 降压模块 | 可选 | 外场电源稳定 | 输入按电池选择，输出 5V/3A 以上更稳 |
| USB 摄像头 | 1 | 视觉桥接 | PC 侧运行 OpenCV/YOLO |
| 杜邦线、面包板、共地线 | 若干 | 联调 | 串口必须共 GND |

## NodeA ESP32-S3 引脚

| 功能 | NodeA 引脚 | 连接对象 | 说明 |
| --- | --- | --- | --- |
| LD2450 RX | GPIO18 | LD2450 TX | `RadarBaudRate=256000` |
| LD2450 TX | GPIO17 | LD2450 RX | 如只读可不接 TX |
| NodeB RX | GPIO15 | NodeB GPIO4 TX | NodeB 身份链输入 |
| NodeB TX | GPIO16 | NodeB GPIO5 RX | 可选，用于后续双向 |
| LD2451 RX | GPIO13 | LD2451 TX | `Ld2451BaudRate=115200` |
| LD2451 TX | GPIO14 | LD2451 RX | 支持后续配置命令 |
| 云台 Pan | GPIO4 | 舵机信号 | 需独立供电时必须共地 |
| 云台 Tilt | GPIO5 | 舵机信号 | 与 Pan 同理 |

## NodeB ESP32-C3 引脚

| 功能 | NodeB 引脚 | 连接对象 | 说明 |
| --- | --- | --- | --- |
| UART TX | GPIO4 | NodeA GPIO15 RX | 必接 |
| UART RX | GPIO5 | NodeA GPIO16 TX | 可选 |
| GND | GND | NodeA GND | 必须共地 |
| 5V/3V3 | 开发板供电口 | USB 或外部电源 | 不建议从信号线取电 |

## 接线原则

- 串口交叉接：`TX -> RX`，`RX <- TX`。
- 所有串口设备必须共 GND。
- LD2451 先用 USB-TTL 单测，再接 NodeA。
- USB-TTL 选择 `USB 转 TTL`，不是 `USB 转 RS485`，也不是 `RS232 转 RS485`。
- 外场长线测试时，优先把供电和信号线固定好，避免移动导致误判为算法问题。

## 给小白的解释

你现在至少需要一块 S3 做 NodeA、一块 C3 做 NodeB。LD2451 接 NodeA 的第二路串口，C3 只负责把身份链/协同信息发给 S3，不负责替代主控。
