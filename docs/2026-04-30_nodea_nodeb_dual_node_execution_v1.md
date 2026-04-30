# 2026-04-30 NodeA + NodeB 双节点联调执行版 V1

## 1. 当前口径锁定

五一真实硬件联调统一叫：

```text
NodeA + NodeB 双节点联调
```

不要把当前硬件直接叫成 `A1 + A2` 两个完整感知节点。

- `NodeA`：ESP32-S3 主感知节点，负责 LD2450、后续 LD2451、云台、主状态输出。
- `NodeB`：ESP32-C3 辅助身份链/通信节点，负责心跳、RSSI、BLE/Wi-Fi/RID 线索，通过 UART 发给 NodeA。
- `A1 + A2`：后续扩展口径，表示两个完整感知节点之间的接力/协同，需要第二套主控和传感器。

答辩表述：

> 当前样机阶段采用 NodeA 主感知节点 + NodeB 辅助身份链节点的双节点协同架构，先验证边缘节点通信、状态同步和身份链补充能力。A1/A2 完整感知节点接力作为后续多节点部署扩展方向，当前通过字段预留和仿真证据支撑。

## 2. 硬件连接

默认主固件配置：

```text
NodeA ESP32-S3 Serial2 RX = GPIO15
NodeA ESP32-S3 Serial2 TX = GPIO16
Baud = 115200
```

NodeB C3 示例工程默认配置：

```text
NodeB ESP32-C3 UART1 TX = GPIO4
NodeB ESP32-C3 UART1 RX = GPIO5
Baud = 115200
```

接线：

```text
NodeB GPIO4 TX  ->  NodeA GPIO15 RX
NodeB GPIO5 RX  <-  NodeA GPIO16 TX   可选，第一轮可不接
NodeB GND       ->  NodeA GND
```

第一轮建议 NodeA 和 NodeB 各自 USB 供电，只共地，不从 S3 给 C3 供电。

## 3. 烧录内容

NodeA 烧录根目录主固件。

NodeB 烧录：

```text
examples/nodeb_c3_identity_uart
```

NodeB 会自动发送：

```text
NODEB,HEARTBEAT,node=B1,source=BLE_WIFI,status=OK,rssi=-62,ble=1,wifi=1
NODEB,RID,node=B1,source=BLE,rssi=-62,status=SEEN,id=TEST-RID-001,auth_status=VALID,whitelist_tag=PENDING
```

## 4. 联调步骤

1. 先只运行 NodeA，确认原 LD2450、云台、主串口输出正常。
2. 烧录并运行 NodeB，先看 C3 USB 串口是否每秒输出 `[NODEA_TX] NODEB,HEARTBEAT...`。
3. 连接 NodeB GPIO4 TX 到 NodeA GPIO15 RX，并共地。
4. 打开 NodeA 串口，确认出现 `NODEB status updated.` 或 `NODEB RID message accepted.`。
5. 在 NodeA 输出里检查 `nodeb_online=1`、`nodeb_node_id=B1`、`nodeb_source=BLE`、`nodeb_rssi`。
6. 拔掉 NodeB 或按复位，NodeA 不应阻塞或崩溃，约 3 秒后进入超时/离线状态。
7. NodeA 原有 LD2450 跟踪、云台、事件字段继续正常。

## 5. 验收标准

- NodeB 心跳能进入 NodeA：`nodeb_online=1`。
- NodeB RID 能进入 NodeA：`rid_id=TEST-RID-001` 或 RID 状态变化可见。
- NodeB 掉线/重启时 NodeA 不阻塞、不崩溃。
- 原 v1.0 六个基线场景不回归。
- 当前只验收 NodeA + NodeB 协同，不验收 A1 + A2 完整接力。

## 6. 下一步

NodeA + NodeB 稳定后，再接入 LD2451：

```text
NodeA + NodeB PASS
-> USB-TTL 单测 LD2451
-> LD2451 接 NodeA 新 UART
-> 再打开 far_motion_trigger 字段验证
-> 最后才考虑融合算法开关
```
