# Flytotal v5.2 Co-Sensing Design V1

Last updated: 2026-05-01

## 当前双节点定义

当前可执行的双节点联调是：

- `NodeA`: ESP32-S3 主感知节点，接 LD2450、LD2451、云台、视觉状态、NodeB 串口身份链。
- `NodeB`: ESP32-C3 辅助身份链/通信节点，先通过 UART 给 NodeA 发送身份链和在线状态。

早期说的 `A1 + A2` 是两个完整感知节点的未来形态；现在先把 `NodeA + NodeB` 打通，保证演示可落地。

## 三段证据链

| 层级 | 证据 | 当前状态 |
| --- | --- | --- |
| UART 字段契约 | `nodeb_online / nodeb_status / handoff_from / handoff_to / continuity_hint` | 主链已接入 |
| ESP-NOW demo | `examples/d_esp_now_signal_sender/` 双向通信 | 作为真实通信证据 |
| 协同仿真 | `tools/co_sensing_simulator.py` | 可生成 handoff 状态机 JSON |

## Handoff 状态机

```text
SINGLE_NODE -> HANDOFF_PENDING -> HANDOFF_ACTIVE -> HANDOVER_DONE
```

- `SINGLE_NODE`: 只有本节点独立工作。
- `HANDOFF_PENDING`: 目标接近边界，邻节点在线，准备接力。
- `HANDOFF_ACTIVE`: 接力过程进行中。
- `HANDOVER_DONE`: 接力完成，事件连续性字段保留。

## v5.2 范围

v5.2 先做到：

- NodeA 不因 NodeB 掉线阻塞。
- NodeB 在线状态进入主状态和大屏。
- 仿真器能跑出边界穿越和 handoff 过程。
- ESP-NOW demo 可用串口日志统计 ACK、延迟和丢包。

完整主固件 ESP-NOW handoff 状态机可以放到 v5.3。

## 给小白的解释

这是什么：一个主节点负责探测，另一个小节点先负责身份链和通信，让系统看起来不是单机。

有什么用：答辩时可以说明 ESP32 不只是“接线板”，而是边缘节点，可以协同感知。

你现在该怎么做：先测 `NodeA + NodeB` 串口联调，再烧 ESP-NOW demo 做通信证据，最后跑协同仿真生成状态机记录。
