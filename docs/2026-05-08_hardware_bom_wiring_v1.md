# v5.2 硬件 BOM 与接线表

## 1. 物料清单

| 模块 | 建议型号 | 数量 | 参考单价 | 工作电压 | 估算电流 | 用途 |
| --- | --- | ---: | ---: | --- | ---: | --- |
| NodeA 主控 | ESP32-S3 DevKitC / S3 N8 | 1 | 30-60 元 | 5V USB / 3.3V IO | 150-300mA | 主控、融合、串口、大屏输出 |
| NodeB 节点 | ESP32-C3 SuperMini | 1 | 15-30 元 | 5V USB / 3.3V IO | 80-180mA | 身份链、协同节点、后续 ESP-NOW |
| 近距雷达 | LD2450 | 1 | 按采购价 | 5V/3.3V 视模块 | 约 100mA | 近距航迹、云台角度链 |
| 远距触发 | LD2451 | 1 | 按采购价 | 5V/3.3V 视模块 | 约 100-200mA | 远距运动预警，不做无人机专用识别 |
| 串口调试 | USB 转 TTL CH340/CP2102 | 1 | 5-20 元 | USB | - | LD2451 单测、串口排错 |
| 视觉输入 | USB 摄像头 | 1 | 按采购价 | USB | 100-500mA | PC 侧视觉确认和证据固化 |
| 显示可选 | OLED 0.96 SSD1306 I2C | 0-1 | 5-15 元 | 3.3V/5V | 20-40mA | 本地调试显示 |
| 告警可选 | 有源蜂鸣器模块 | 0-1 | 2-8 元 | 3.3V/5V | 10-40mA | 本地声音告警 |
| 电源可选 | DC-DC 降压模块 LM2596/MP1584 | 0-1 | 5-30 元 | 按电池输入 | 视负载 | 外场供电稳定 |
| 连接材料 | 杜邦线、面包板、共地线 | 若干 | - | - | - | 联调接线 |

供应商记录建议单独在采购表里补：平台、店铺、链接、下单日期、到货日期、实付价格、是否开票。

## 2. 功率预算

| 组合 | 估算电流 | 建议供电 |
| --- | ---: | --- |
| NodeA + LD2450 + LD2451 | 350-700mA | 稳定 5V/1A 以上 |
| NodeA + 双雷达 + 舵机 | 800mA-2A 峰值 | 舵机独立 5V/2A，必须共 GND |
| NodeA + NodeB + 双雷达 | 450-900mA | 两块板可各自 USB，必须共 GND |
| 外场完整演示 | 1A-3A 峰值 | 建议移动电源或 DC-DC 降压，避免从弱 USB 口取电 |

注意：舵机抖动、雷达假断连、串口乱码，经常不是算法问题，而是供电压降或 GND 没共好。

## 3. NodeA ESP32-S3 引脚表

| 功能 | NodeA 引脚 | 连接对象 | 波特率/说明 |
| --- | --- | --- | --- |
| LD2450 RX | GPIO18 | LD2450 TX | `RadarBaudRate=256000` |
| LD2450 TX | GPIO17 | LD2450 RX | 只读时可不接 |
| NodeB RX | GPIO15 | NodeB GPIO4 TX | `NodeBBaudRate=115200` |
| NodeB TX | GPIO16 | NodeB GPIO5 RX | 可选，后续双向 |
| LD2451 RX | GPIO13 | LD2451 TX | `Ld2451BaudRate=115200` |
| LD2451 TX | GPIO14 | LD2451 RX | 支持后续配置命令 |
| 云台 Pan | GPIO4 | Pan 舵机信号 | 舵机供电建议独立 |
| 云台 Tilt | GPIO5 | Tilt 舵机信号 | 与 Pan 共地 |

## 4. NodeB ESP32-C3 引脚表

| 功能 | NodeB 引脚 | 连接对象 | 说明 |
| --- | --- | --- | --- |
| UART TX | GPIO4 | NodeA GPIO15 RX | 必接 |
| UART RX | GPIO5 | NodeA GPIO16 TX | 可选 |
| GND | GND | NodeA GND | 必须共地 |
| 5V/3V3 | 开发板供电口 | USB 或外部电源 | 不从信号线取电 |

## 5. ASCII 接线图

```text
          USB/PC
            |
     +--------------+
     | NodeA ESP32-S3|
     |              | GPIO18 RX <--- LD2450 TX
     |              | GPIO17 TX ---> LD2450 RX
     |              |
     |              | GPIO13 RX <--- LD2451 TX
     |              | GPIO14 TX ---> LD2451 RX
     |              |
     |              | GPIO15 RX <--- NodeB GPIO4 TX
     |              | GPIO16 TX ---> NodeB GPIO5 RX (optional)
     |              |
     |              | GPIO4  ----> Pan servo signal
     |              | GPIO5  ----> Tilt servo signal
     +--------------+
            | GND -------------------+
                                    |
                              +------------+
                              | NodeB C3   |
                              +------------+
```

## 6. 采购和接线选择

- LD2451 单测需要 `USB 转 TTL`，不要买 RS485 或 RS232 转 RS485。
- OLED 选 `0.96 inch SSD1306 I2C 4针`，不是 SPI 7 针，避免占用更多线。
- 蜂鸣器选有源蜂鸣器，高电平触发或高低电平可选款都可以，先不作为主链必需。
- TF 卡和 SD 模块不是 P0 必需，证据优先存在 PC 的 `outputs/` 和 `captures/`。
- 逻辑分析仪不是必须，但如果串口乱码、帧丢失、波特率不确定，它会明显节省排错时间。

## 7. 给小白的解释

你现在至少需要一块 S3 做 NodeA、一块 C3 做 NodeB。LD2451 接 NodeA 的第二路串口，C3 只负责把身份链/协同信息发给 S3，不负责替代主控。所有串口设备都要共 GND，这是比算法更先检查的事情。
