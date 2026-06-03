# Flytotal 现场测试完整指南 V1

更新：2026-05-25 · 整理自 2026-05-25 系列对话 · 答辩演示 + 现场调试用

---

## 0. 这份文档的来历

本文档汇总学生提出的 6 大类现场测试问题 + 系统答复，覆盖：白名单机制 / 合作判定 / 硬件状态 / 舵机行为 / 自动化矩阵 / UWB 升级候选。**目标**：演示前打印一份，现场翻；评委追问时答得上。

**配套文档**：
- `docs/2026-05-08_v5_2_runbook_v1.md` — 编译 + 烧录 + 跑通
- `docs/2026-05-16_demo_submission_runbook_v1.md` — 答辩日 SOP
- `docs/2026-04-30_v5_2_defense_qa_v1.md` — 12 项 Q&A
- `docs/2026-05-09_exec_summary_v1.md` — 一页摘要

---

## 1. 学生提出的全部问题清单

| # | 问题 | 本文档章节 |
|---|---|---|
| 1 | 现场呈现应该是什么样子？各硬件状态？怎么测？ | §3, §4, §6 |
| 2 | 怎么知道目标是不是白名单？怎么判合作 vs 非合作？ | §2 |
| 3 | 现场测试时，测试物体 / 被测试物体 / 硬件应该是什么状态什么动作？ | §3, §6 |
| 4 | 舵机呢？舵机会不会跟着被测试目标动？需不需要舵机？ | §5 |
| 5 | 白名单 / 合作判定 / 抓拍 / 跟踪是不是都自动？还是要人为？ | §7 |
| 6 | 低空毫米波距离够不够？UWB 加上去更有冲击力吗？ | §8 |

---

## 2. 白名单 + 合作目标判定逻辑

### 2.1 白名单本质

**硬编码在固件里**，编译时定死，运行时不能改。代码位置 `src/main.cpp:503-508`：

| RID | 是否允许 | 用途 |
|---|---|---|
| `SIM-RID` | ✅ 允许 | TeamA 通用合法目标 |
| `SIM-RID-001` | ✅ 允许 | **演示合作目标**（默认 NodeB 广播这个）|
| `SIM-RID-999` | ❌ 拒绝 | **演示非合作目标** |
| `SIM-RID-EXPIRED` | ⏰ 已过期 | 演示白名单过期场景 |

要切换合作 / 非合作必须**重新烧 NodeB**（编译时 `-D NODEB_RID_ID=SIM-RID-999`），不能运行时切。

### 2.2 RID 接收路径（NodeA 收到 RID 怎么处理）

```
NodeB C3 (3s 一次广播)
    ↓ UART 115200
RID,MSG,<rid_id>,<device_type>,NODE_B,<ts>,<auth>,<wl_tag>,<rssi>
    ↓ src/main.cpp:679-707 parseRidMessagePayload()
全部字段写入 RidIdentityPacket
    ↓ src/main.cpp:5042-5050
调用 setRidIdentityPacket() → refreshRidRuntime()
    ↓ src/main.cpp:639-677 resolveWhitelistDecision()
查表 → 设置 wl_status (WL_ALLOWED / WL_DENIED / WL_EXPIRED / WL_UNKNOWN)
    ↓ src/main.cpp:765-799
推进 rid_status：NONE → RECEIVED → MATCHED（要求活动航迹 + 白名单允许 + 1200ms 匹配窗内）
```

### 2.3 5 档目标判定（target_verdict）

`deriveTargetVerdict()` 在 `src/main.cpp:2110-2147`，**优先级自上而下短路判定**：

| 优先级 | 判定 | 条件（**全部满足**才进） | UI 颜色 |
|---|---|---|---|
| 1 | **CONFIRMED_COOPERATIVE_DRONE** | `rid_status==RID_MATCHED` AND `wl_status==WL_ALLOWED` AND `rid_whitelist_hit==true` | 🟢 绿 |
| 2 | **VISUALLY_CONFIRMED_DRONE** | `vision_locked==true` AND `vision_confidence≥0.70` AND `bbox_stability≥0.60` AND (radar_track 活动 OR far_motion_trigger) | 🔴 红 |
| 3 | **PROBABLE_MULTIROTOR** | 雷达确认 AND `is_multirotor_like==true` AND `multirotor_score≥65` | 🟡 黄 |
| 4 | **MOTION_ALERT** | `far_motion_trigger==true` | 🟡 黄 |
| 5 | **UNKNOWN_TARGET** | 都不满足 | ⚪ 灰 |

**核心结论**：单纯视觉看到 ≠ 合作目标。**只有 RID 匹配 + 白名单允许 + 命中位 = 1 才是合作目标。**

### 2.4 串口数据示例（你现场会看到这些）

#### NodeB 主动广播（每 3 秒）
```
NODEB,RID,node=NodeB-C3,source=BLE,rssi=-62,status=SEEN,id=SIM-RID-001,auth_status=VALID,whitelist_tag=WL_OK
```
- `node=NodeB-C3`：NodeB 自报名
- `source=BLE`：声称来自 BLE 扫描（实际是模拟）
- `rssi=-62`：信号强度 dBm（典型 -50 到 -80）
- `status=SEEN`：观测到广播
- `id=SIM-RID-001`：核心字段 → 触发白名单查表
- `auth_status=VALID`：声称鉴权通过
- `whitelist_tag=WL_OK`：NodeB 端的标记（NodeA 仍会自己查表）

#### NodeA 把这条解析后产生的格式（host command 通道）
```
RID,MSG,SIM-RID-001,UAV,NODE_B,123456789,VALID,WL_OK,-62
```
共 9 字段，逗号分隔。

#### NodeA 处理后 Dashboard 看到的字段（合作目标场景）
```
rid_id              = "SIM-RID-001"
rid_device_type     = "UAV"
rid_source          = "NODE_B"
rid_signal_strength = -62
rid_auth_status     = "VALID"
rid_whitelist_tag   = "WL_OK"
rid_status          = RID_MATCHED        ← 状态机自动推进
wl_status           = WL_ALLOWED         ← 查表结果
rid_whitelist_hit   = 1                  ← 命中位
wl_owner            = "LabA"             ← 来自白名单表
wl_label            = "UAV-001"          ← 来自白名单表
wl_note             = "RID,MSG 合法样例" ← 来自白名单表
target_verdict      = "CONFIRMED_COOPERATIVE_DRONE"
```

#### 非合作（SIM-RID-999）会看到
```
rid_status          = RID_INVALID        ← 状态机判定无效
wl_status           = WL_DENIED          ← 表里 allowed=false
rid_whitelist_hit   = 0
wl_owner            = "LabA"             ← 仍有元数据
wl_label            = "UAV-999"
wl_note             = "不在允许名单"
target_verdict      = "VISUALLY_CONFIRMED_DRONE"（如果视觉锁定）
                     或 "UNKNOWN_TARGET"（如果视觉没锁定）
```

#### 完全没收到 RID（NodeB 离线）
```
rid_status          = RID_NONE           ← 啥都没收到
wl_status           = WL_UNKNOWN
rid_whitelist_hit   = 0
nodeb_online        = 0                  ← 3 秒后转 false
nodeb_status        = "OFFLINE_OR_TIMEOUT"
```

### 2.5 现场调试命令（白名单 / RID 相关）

```bash
# 手动注入一条 RID（不依赖 NodeB），用于断网测试
echo "RID,MSG,SIM-RID-001,UAV,USB,$(date +%s%3N),VALID,WL_OK,-50" > /dev/tty.usbserial-XXX

# 注入非合作 RID
echo "RID,MSG,SIM-RID-999,UAV,USB,$(date +%s%3N),VALID,WL_OK,-50" > /dev/tty.usbserial-XXX

# 注入完全未知 RID（不在表里）
echo "RID,MSG,UNKNOWN-RID,UAV,USB,$(date +%s%3N),VALID,WL_OK,-50" > /dev/tty.usbserial-XXX
# 结果：wl_status=WL_UNKNOWN, rid_whitelist_hit=0

# 注入已过期白名单
echo "RID,MSG,SIM-RID-EXPIRED,UAV,USB,$(date +%s%3N),VALID,WL_OK,-50" > /dev/tty.usbserial-XXX
# 结果：wl_status=WL_EXPIRED, rid_whitelist_hit=0

# 查询当前 RID 状态
echo "RID,STATUS" > /dev/tty.usbserial-XXX
# 串口返回：RID,STATUS,id=...,status=...,wl=...

# 查询融合状态
echo "FUSION,STATUS" > /dev/tty.usbserial-XXX
```

### 2.6 白名单查表的边界用例

| 场景 | rid_id | 表内 allowed | expire_time | 结果 wl_status | hit |
|---|---|---|---|---|---|
| 标准合作 | SIM-RID-001 | true | 0（永不过期） | WL_ALLOWED | 1 |
| 拒绝列表 | SIM-RID-999 | false | — | WL_DENIED | 0 |
| 已过期 | SIM-RID-EXPIRED | true | 1000（远小于 now） | WL_EXPIRED | 0 |
| 不在表内 | RANDOM-XXX | — | — | WL_UNKNOWN | 0 |
| 空字段 | "" | — | — | WL_UNKNOWN | 0 |
| 大小写混合 | sim-rid-001 | true | 0 | **WL_ALLOWED**（不区分大小写）| 1 |

### 2.7 想现场加新白名单怎么办

**编译期才能改**（运行时不支持）。流程：

1. 修改 `src/main.cpp:503-508` 的 `RidWhitelistTable[]`，加新条目：
   ```cpp
   {"DJI-MAVIC-PRO-12345", "我的实验室", "Mavic Pro", true, 0, "答辩用合作无人机"},
   ```
2. 重新 `pio run -t upload`（30 秒）
3. NodeB 也要烧成广播这个 RID：
   ```cpp
   // examples/nodeb_c3_identity_uart/src/main.cpp:20
   #define NODEB_RID_ID "DJI-MAVIC-PRO-12345"
   ```

如果带真无人机（如 DJI Mini 3），它的 Remote-ID 是飞行器序列号，**当前 NodeB 不会扫真实 Wi-Fi/BLE 广播**（v5.3 计划），所以现场要么：
- 把 DJI 的序列号写入白名单表（演示前查 DJI 设置）
- 或者**完全不用 RID 路径**，让真无人机走 VISUALLY_CONFIRMED_DRONE 路径

---

## 3. 现场布置 + 硬件清单

### 3.1 演示桌结构

```
                    📐 Pan/Tilt 云台
                    ┌──────────┐
                    │  📷 摄像头 │← 装云台上随动
                    └────┬─────┘
                         │
                    ┌────┴─────┐
                    │  Pan 舵机 │← GPIO 4
                    │  Tilt 舵机│← GPIO 5
                    └────┬─────┘
                         │
       ┌─────────────────┴─────────────────┐
       │       三脚架 / 底座（固定）         │
       │   📡 LD2450 ─── 📡 LD2451         │
       │   📋 NodeA      📋 NodeB           │
       └─────────────────┬─────────────────┘
                         │ USB Hub
                  ┌─────────────┐
                  │  💻 笔记本   │
                  │  Dashboard  │
                  └─────────────┘
```

**重要**：摄像头**必须装在 pan-tilt 云台上**，否则舵机转 → 视野不跟随 → 跟踪逻辑无意义。
**bore-sight 对齐**：摄像头视轴和雷达正前方对齐，否则雷达 (x,y) 转 pan/tilt 角度会偏。

### 3.2 NodeA 主感知节点（演示桌核心）

| 硬件 | 数量 | 在做什么 | 引脚 / 物理表现 |
|---|---:|---|---|
| **ESP32-S3 主板** | 1 + 备用 1 | 跑融合 / 事件 / 云台主控 | 板载 LED 常亮 |
| **LD2450 短距 2D 雷达** | 1 | 5-30m 距离 + xy 坐标 + 速度 | RX=18 / TX=17，256000 baud；上电常亮 |
| **LD2451 长距运动雷达** | 1 | 30-100m 远距运动触发 | RX=13 / TX=14，115200 baud；上电常亮 |
| **USB 摄像头** | 1 + 备 1 | 视觉跟踪 + YOLO 检测 | USB；LED 亮，有图像 |
| **Pan 舵机（水平）** | 1 | **跟踪目标转动** | GPIO 4，50Hz PWM，10°-170°（中心 90°） |
| **Tilt 舵机（垂直）** | 1 | **跟随目标距离俯仰** | GPIO 5，50Hz PWM，60°-120°（中心 90°） |
| **三脚架 / 云台底座** | 1 | 固定整套设备 | 静止 |
| **NodeB（C3）接收板** | 1 | 接收身份链 RID（UART → NodeA UART2） | RX=15 / TX=16，115200 baud |

### 3.3 被测目标侧硬件（演示用 2-3 套）

| 硬件 | 用途 | 携带者 |
|---|---|---|
| **ESP32-C3 + 充电宝（烧 SIM-RID-001）** | 合作目标 | 同学 1 |
| **ESP32-C3 + 充电宝（烧 SIM-RID-999）** | 非合作目标（带 RID 但被拒）| 同学 2 |
| **DJI Mini 3 无人机**（如有）| 真无人机演示 | 操作员 |
| **行人 / 自行车 / 汽车** | 干扰对照 | 临时配合 |

### 3.4 上位机

| 硬件 | 用途 |
|---|---|
| **笔记本** | 跑 vision_bridge + vision_web_server + 浏览器 Dashboard |
| **备用笔记本** | 主笔记本死机时切换 |
| **USB Hub 多口** | 接 NodeA + 摄像头 + NodeB 直连 USB |

### 3.5 现场没有的物理告警（重要短板）

⚠️ **当前固件无 LED 警报灯 / 蜂鸣器 / OLED 显示屏**。所有告警**只有舵机动作 + Dashboard 显示**。
评委如果看不到 Dashboard，只能靠**舵机的剧烈跟踪**感知系统在工作。

**可选增强**（如果时间允许）：
- 接 1 个红色 LED + 蜂鸣器到 NodeA 空闲 GPIO（1h 硬件 + 30min 代码挂 `trigger_alert`）
- 接 OLED I2C 屏 SSD1306 128×64 显示 risk_level + verdict（1h + 1h）
- 舵机指端加激光笔（0.5h）可视化跟踪方向

---

## 4. 各硬件正常状态对照表

| 硬件 | 开机自检 | 静止待机 | 检测到目标 | EVENT 触发 |
|---|---|---|---|---|
| **NodeA LED** | 闪烁 | 常亮 | 常亮 | 常亮（无变化）|
| **NodeA 串口** | 启动 1-3s 内打印 `BASELINE,VERSION=Node_A_Base_Demo_V1.1` + `Node A control chain starting` | 1Hz `HB,now=...,risk=NORMAL,...` | 同上+ track/risk 字段变化 | 4Hz 加密输出 |
| **LD2450** | 上电亮 | Dashboard 数据全 0 | `x_mm / y_mm / vx / vy` 实时变化，`track_active=true` | 同上 |
| **LD2451** | 上电亮 | `ld2451_valid=false` | `lr_range_m` 有值、`ld2451_valid=true` | `far_motion_trigger=true` |
| **摄像头** | 看到画面 | 静止画面 | 绿框 + 红框跟着目标动 | 视觉区"已抓拍"标记 |
| **Pan 舵机** | 中心 90° | 🔄 **±15° 摇头扫描**（SCANNING）| 🎯 转向目标（ACQUIRING）| 🎬 实时跟踪（TRACKING）|
| **Tilt 舵机** | 中心 90° | 固定 90° | 跟着 y_mm 距离俯仰 | 同上 |
| **NodeB LED** | 闪烁 | 1Hz 心跳闪 | 1Hz 心跳闪（不变）| 同上 |
| **NodeB 串口** | 启动后开始发 | 1Hz `NODEB,HB,...` + 3s 一次 `NODEB,RID,...,id=SIM-RID-001,...` | 同上 | 同上 |
| **Dashboard** | 全绿 + UNKNOWN_TARGET 灰 | 8 tab 渲染正常，2s 刷新 | verdict pill 变色 | 🔴 红色 verdict + 抓拍 |

---

## 5. 舵机详解（学生重点关心）

### 5.1 舵机会跟着目标动 ✅

**配置**（`include/AppConfig.h` ServoConfig + GimbalConfig）：
- Pan：GPIO 4，50Hz PWM，500-2500µs 脉宽，**范围 10°-170°，中心 90°，可摆左右各 80°**
- Tilt：GPIO 5，50Hz PWM，500-2500µs 脉宽，**范围 60°-120°，中心 90°，可摆上下各 30°**
- **更新频率 50Hz**（每 20ms 写一次新角度）
- **平滑跟踪**，配 PD + 加速度 clamp + 低通滤波，不会抽搐

### 5.2 4 个状态对应的物理动作

| 状态 | 触发 | 舵机做什么 | 现场观感 |
|---|---|---|---|
| **STATE_SCANNING** | 启动后无目标 | Pan 左右扫扇形 ±15°，周期 ~0.9Hz；Tilt 90° 固定 | 🔄 **持续左右摇头**，像探照灯巡逻 |
| **STATE_ACQUIRING** | 雷达发现目标但不满 5 帧 | Pan 转向目标方向 | 🎯 **突然停下转向目标** |
| **STATE_TRACKING** | 目标确认（≥5 帧） | 实时跟随 + 180ms 提前量预测；Tilt 跟 y_mm 距离 | 🎬 **平滑跟着目标动**，自然 |
| **STATE_LOST** | 目标丢失 >3 秒 | 保持最后角度 → 回到 SCANNING | ⏸️ 停 3s → 重新摇头扫描 |

**关键代码**：`lib/GimbalController/GimbalController.cpp` 状态机 + `lib/GimbalPredictor/GimbalPredictor.cpp` 二阶外推。

### 5.3 雷达坐标 → 舵机角度的转换

**Pan（水平）转换**（`GimbalPredictor::calculateFiringAngle()`）：
```
target_x_mm, target_y_mm （雷达坐标系，单位 mm）
  ↓ atan2(x, y) → 弧度
  ↓ rad * 180 / π → 度
  ↓ +90°（中心偏移，雷达正前方 = 0°，舵机 90° = 正前方）
  ↓ clamp(10°, 170°)
target_pan_deg
  ↓ Kp * error + Kd * d_error / dt   ← PD 控制
  ↓ +180ms 提前量（vx 预测）
  ↓ +加速度补偿 0.5 * ax * t²（受 ±5000mm/s² clamp + LPF α=0.7）
final_pan_deg
```

**Tilt（垂直）转换**（线性映射）：
```
target_y_mm （前向距离）
  ↓ map(0 - 6000 mm) → (60° - 120°)
final_tilt_deg
```
- 近距离（y_mm 小）→ tilt 角度小（向上）
- 远距离（y_mm 大）→ tilt 角度大（向下）

**关键参数**（`include/AppConfig.h`）：
- `PredictorKp = 0.45` — 比例增益
- `PredictorKd = 0.05` — 微分增益
- `PredictorLeadTimeSeconds = 0.18` — 180ms 提前量
- `PredictorMaxAccelMmS2 = 5000` — 加速度上限
- `PredictorLpfAlpha = 0.7` — 低通滤波系数

### 5.4 4 个状态详细行为参数

| 状态 | Pan 行为 | Tilt 行为 | 退出条件 |
|---|---|---|---|
| SCANNING | `90° + 15° * sin(t / 900ms)` 正弦扫描 | 固定 90° | 出现 track_active=true |
| ACQUIRING | 转向目标，无 PD 阻尼 | 跟距离 | 150ms 内 track 持续 → TRACKING |
| TRACKING | PD + 180ms 提前量 + 二阶外推 | 跟距离 | track_active=false 且持续 3s → LOST |
| LOST | 保持最后角度 | 保持最后角度 | 3s 后 → SCANNING |

### 5.5 舵机选型推荐

| 型号 | 力矩 | 优点 | 缺点 | 推荐度 |
|---|---|---|---|---|
| **SG90** | 1.8 kg·cm | 便宜（¥5）、轻 | **带不动摄像头**、抖动大 | ❌ 不推荐 |
| **MG90S** | 2.5 kg·cm | 金属齿、便宜（¥15） | 力矩对重摄像头仍紧张 | ⚠️ 勉强够（轻摄像头）|
| **MG996R** | 11 kg·cm | 力矩大、稳 | 偏重、需独立电源 | ✅ **推荐** |
| **DS3225** | 25 kg·cm | 稳定、数字舵机 | 贵（¥60+） | ✅ 高端选择 |

### 5.6 舵机电源接线（这是新手最易翻车点）

❌ **错误接法**：舵机 V+ 接 ESP32 板载 5V → ESP32 电流不够 → 舵机抖动甚至重启
✅ **正确接法**：

```
   独立 5V/3A 电源（如 5V 充电宝 + USB 转接）
        │
        ├──── 舵机1 V+
        ├──── 舵机2 V+
        │
        └──── 共地 ───── ESP32 GND
                     │
                     └──── 信号线 ──→ ESP32 GPIO 4/5
```

**关键**：舵机 V+ 走独立电源，GND 和 ESP32 共地，信号线接 ESP32 GPIO。

### 5.7 现场可能的舵机问题（详细排查）

| 问题 | 现场表现 | 根因 | 应急 |
|---|---|---|---|
| 舵机抖动剧烈 | Pan 不停跳动 | 加速度 clamp 不够 | 调大 `PredictorMaxAccelMmS2` 至 8000 |
| 舵机偶发抖一下 | 1 秒内突然跳 30° 又回 | 雷达数据 NaN/Inf 穿透 | 已有 isfinite() 守卫，若仍有 → 改高阈值 |
| 舵机不动 | SCANNING 时不摇头 | 电源不够 / GPIO 接错 | 检查 GPIO 4/5 + 独立 5V 电源 |
| 舵机持续转圈 | 一直顺时针/逆时针转 | 信号线短路或 PWM 频率错 | 检查 50Hz + 脉宽 500-2500µs |
| 舵机响声大 | "嗡嗡"持续声 | 舵机被堵转（机械干涉） | 检查云台是否被卡住、舵机轴是否对齐 |
| 摄像头不在云台上 | 跟踪逻辑无效化 | 物理没装 | 立刻装 / 或口头降低预期 |
| Pan 极限角抽搐 | 接近 10° 或 170° 跳 | clamp 边界震荡 | 收窄到 30°-150° |
| 舵机电源烧 | 蜂鸣冒烟 | 短路 / 过压 | 备用舵机 + 限流电源 |
| 摄像头 USB 线绊住云台 | 转动卡顿 | 线路布局不当 | 用导线管或绑带固定走线 |
| Tilt 不跟距离动 | y_mm 变化但 Tilt 固定 | 线性映射超出 6000mm 范围 | 改 `MaxTiltMapInputMm` 至 10000 |

### 5.8 舵机测试命令

```bash
# 强制舵机回中心（用于 demo 前归位）
echo "GIMBAL,CENTER" > /dev/tty.usbserial-XXX

# 手动设置舵机角度（绕过算法，用于硬件验证）
echo "GIMBAL,SET,pan=90,tilt=90" > /dev/tty.usbserial-XXX

# 跑舵机扫描自检（左右各扫一次）
echo "GIMBAL,SWEEP" > /dev/tty.usbserial-XXX

# 关闭舵机输出（演示时担心舵机干扰其他展示）
echo "GIMBAL,DISABLE" > /dev/tty.usbserial-XXX

# 重新启用
echo "GIMBAL,ENABLE" > /dev/tty.usbserial-XXX
```

> **注意**：这些 host command 部分尚未实装，需查 main.cpp 当前支持的命令清单。当前确认存在的命令：`FUSION,ENABLE,0/1`、`FUSION,STATUS`、`VISION,CONF,...`、`RID,STATUS`、`LD2451,SELFTEST`、`CONFIG,STATUS`。GIMBAL 类命令需补开发。

---

## 6. 演示动作脚本（8 分钟剧本）

### 角色分工（建议 2-3 人）

| 角色 | 职责 |
|---|---|
| **解说员**（你）| 讲技术、操作笔记本、按需发回退命令 |
| **被测目标 A**（同学 1）| 手持 NodeB 合作目标盒子（C3 + 充电宝），扮合作无人机 |
| **被测目标 B**（同学 2）| 不带 RID 或带 SIM-RID-999，扮非合作无人机 |
| **干扰物** | 行人 / 自行车，由观众或临时同学扮演 |

### T+0:00 ~ 0:30 — 开场（静止）

**所有人**：站在画面外
**Dashboard 状态**：全绿 / `target_verdict=UNKNOWN_TARGET` / `track_active=false` / `nodeb_online=true`

> "这是 NodeA + 双雷达 + 摄像头 + NodeB 边缘协同节点的反无人机检测系统。FAR/MID/NEAR 分阶段融合算法，100m 远距广搜，30m 中距确认，10m 近距固证。看 Dashboard——4 个传感器全在线，risk_level=NORMAL，空闲状态。"

### T+0:30 ~ 2:00 — 合作目标演示

**同学 1**：拿着 NodeB 盒子从右侧走入视野

**Dashboard 时序变化**：

| 时刻 | 看到什么 | 解说词 |
|---|---|---|
| 入场 | `track_active=true` + `vision_locked=true` | "雷达和视觉同时检测到目标" |
| +1-2s | `track_confirmed=true`（≥5 帧）+ 视觉区出现绿框 + 红框 | "目标确认，5 帧稳定后进入跟踪" |
| +1-2s | `rid_status: RECEIVED → MATCHED` | "NodeB 收到 RID 广播，1.2 秒匹配窗内对上" |
| +1s | **`target_verdict=CONFIRMED_COOPERATIVE_DRONE`** 🟢 | "RID + 白名单 + 命中位三个条件齐了，判定为合作无人机" |
| 持续 | `risk_level=NORMAL`, `event_active=0` | "合作方**不触发告警事件**，这是核心" |

**同学 1**：在视野中走动 10 秒 → 走出

### T+2:00 ~ 4:00 — 非合作目标演示

**选项 A（推荐）**：同学 1 关 NodeB（拔充电宝）退场；同学 2 入场

**Dashboard 时序变化**：

| 时刻 | 看到什么 | 解说词 |
|---|---|---|
| 同学 1 退场 + NodeB 关 | `nodeb_online=false`（3s 后）+ `rid_status=NONE` | "NodeB 离线，无 RID 来源" |
| 同学 2 入场 | `track_active=true` + `vision_locked=true` | "雷达 + 视觉锁定，但**没有 RID**" |
| +2s | **`target_verdict=VISUALLY_CONFIRMED_DRONE`** 🔴 | "视觉 + 雷达 - RID = 视觉确认（非合作）" |
| +3-5s | `risk_level=SUSPICIOUS → HIGH_RISK` | "风险逐级上升" |
| +10s | `risk_level=EVENT`, `event_active=1`, "已抓拍" | "触发事件，自动抓拍" |

**选项 B**（更刺激，需烧 2 块 NodeB）：同学 2 拿带 SIM-RID-999 的盒子 → `wl_status=WL_DENIED`

### T+4:00 ~ 5:30 — 分阶段融合演示

**同学 1**：从远端慢慢走近（如场地允许 30m 起步）

| 距离 | `fusion_stage` | 触发条件 | 解说 |
|---|---|---|---|
| >30m | `FAR` | LD2451 + RID 双源 | "远距广搜，LD2451 给运动 + RID 验合作身份" |
| 10-30m | `MID` | 2 源一致 + 距离一致性 | "中距确认，LD2450 加入，一致性校验" |
| <10m | `NEAR` | 必须视觉或 RID_MATCHED | "近距固证，视觉锁定 + 多旋翼评分" |

### T+5:30 ~ 6:30 — 抗干扰演示

**动作**：同学 1 退场（NodeB 留桌）→ 请观众 / 同学走过 / 自行车骑过

| 干扰物 | `is_multirotor_like` | `multirotor_score` | `target_verdict` | 解说 |
|---|---|---:|---|---|
| 行人（1-1.5 m/s）| false | <40 | UNKNOWN / MOTION_ALERT | "速度低于 2 m/s 区间，不符合多旋翼" |
| 自行车（4-6 m/s）| false | 50-60 | 同上 | "速度匹配但持续时长 / 悬停方差不对" |
| 站立不动 | false | ~0 | UNKNOWN | "速度方差太低" |

> "行人、自行车不会被错判，risk_level 始终 ≤ MID，**不会进入 EVENT**。这是算法层抗干扰。"

### T+6:30 ~ 7:00 — 协同感知演示（备选）

如只有 1 个 NodeA，跳过或用 `co_sensing_simulator` JSON + dashboard tab 展示已录历史。

### T+7:00 ~ 8:00 — 回退演示（评委追问时）

> "我演示软回退——立刻把 v5.2 关掉。"

```bash
# 串口终端发命令
FUSION,ENABLE,0
```

Dashboard 立刻：`fusion_stage` 字段消失、行为回 3 源计数模式。

> "1 秒生效。完整回 v1.0 固件 → `git checkout release/v1.0 && pio run -t upload`，30s 重烧。"

⚠️ **前提**：`release/v1.0` tag **当前不存在**，必须先建（见 plan V6 E-1 项）。

### 6.1 完整解说稿（逐分钟版本，可背）

#### 开场（T+0:00 ~ 0:30）30 秒
> "各位评委好，我演示的是基于 ESP32 边缘节点的反无人机感知系统 Flytotal。
> 
> 看这个 Dashboard——
> - 左上角是节点状态：NodeA 主感知节点在线，NodeB 协同节点在线
> - 中间是 4 个传感器卡片：LD2450 短距雷达、LD2451 长距运动雷达、视觉摄像头、NodeB 身份链，全部 OK
> - 右侧是风险等级：risk_level=NORMAL，target_verdict=UNKNOWN_TARGET，空闲状态
> 
> 注意看右下角的云台——舵机正在左右扫描，这是 SCANNING 状态，等待目标。"

#### 合作目标演示（T+0:30 ~ 2:00）90 秒
> "现在我请同学 1 进入视野。他手里拿的是一个 ESP32-C3 节点，模拟一架**合作无人机**——已经通过我们的白名单认证。
> 
> 看 Dashboard：
> - track_active 跳 true，LD2450 锁定
> - 视觉区出现绿色框（CSRT 跟踪）和红色框（YOLO 检测）
> - 约 1 秒后 track_confirmed 跳 true（5 帧确认）
> - 同一时间 NodeB 收到 RID 广播，rid_status 从 NONE 跳到 RECEIVED 再到 MATCHED
> - 关键：wl_status=WL_ALLOWED，白名单查表通过
> 
> 现在看 target_verdict——CONFIRMED_COOPERATIVE_DRONE，绿色。
> 这是核心：合作目标识别需要 RID 匹配 + 白名单允许 + 命中位三个条件同时满足。
> 
> **注意 risk_level 仍然是 NORMAL，event_active=0。系统知道这是合作方，不告警。**
> 
> 看舵机——已经从 SCANNING 切到 TRACKING 状态，平稳跟踪同学 1 的位置。"

#### 非合作目标演示（T+2:00 ~ 4:00）120 秒
> "现在演示非合作目标。请同学 1 退场，关闭 NodeB。
> 
> 看 Dashboard：3 秒后 nodeb_online 变 false，rid_status 回到 NONE。
> 
> 请同学 2 进入。他不带任何 RID 发射器，模拟未授权目标。
> 
> 看变化：
> - track_active=true，视觉锁定，绿框红框出现
> - 但没有 RID，rid_status 保持 NONE
> - 约 2 秒后 target_verdict 变为 VISUALLY_CONFIRMED_DRONE（红色）
> - 因为：视觉 + 雷达确认有目标，但没有合作身份证明
> 
> 注意 risk_level——从 NORMAL → SUSPICIOUS → HIGH_RISK 逐级上升。
> 看右下角 event 卡片：约 10 秒后 event_active 跳 1，触发告警事件，视觉区出现"已抓拍"标记。
> 这一切都是自动完成的，无需任何人工干预。"

#### 分阶段融合演示（T+4:00 ~ 5:30）90 秒
> "现在演示我们的 FAR/MID/NEAR 分阶段融合算法。请同学 1 重新连接 NodeB，从远端慢慢走近。
> 
> 看 fusion_stage 字段：
> - 距离 >30m：FAR 阶段，依靠 LD2451 长距雷达 + RID 双源
> - 距离 10-30m：MID 阶段，LD2450 加入，要求 2 源距离和速度一致性
> - 距离 <10m：NEAR 阶段，必须有视觉锁定或 RID_MATCHED 才能升 HIGH 风险
> 
> 这是'远距广搜、中距确认、近距固证'的策略——
> 远处只给低风险预警避免误报，
> 中距用多源一致性提高可信度，
> 近距用视觉做最终证据固化。"

#### 抗干扰演示（T+5:30 ~ 6:30）60 秒
> "现在演示抗干扰能力。请同学 1 退场，我请一位志愿者从画面走过——这是模拟行人。
> 
> 看：
> - track_active=true，雷达跟到了，舵机也跟过去
> - 但 is_multirotor_like=false，multirotor_score 只有 30 多
> - target_verdict 不会升到 PROBABLE_MULTIROTOR
> 
> 为什么？我们用了 4 维特征筛选：
> - 速度区间 2-25 m/s（行人 1-1.5 m/s 太慢）
> - 持续时长 ≥2s
> - 悬停容忍（速度方差 ≤900 mm/s）
> - 轨迹曲率（航向变化率 ≤75°/s）
> 
> risk_level 始终不会进 EVENT，**不会触发误告警**。这是算法层抗干扰，不是简单的'看到就报'。"

#### 协同感知演示（T+6:30 ~ 7:00）30 秒（备选）
> "这是我们的协同感知 tab。NodeA 和 NodeB 是双节点拓扑，当目标跨越节点视场边界时，handoff 状态机会自动切换：
> SINGLE_NODE → HANDOFF_PENDING → HANDOFF_ACTIVE → HANDOVER_DONE
> 看这段历史记录——这是上次测试时的边界穿越数据。"

#### 回退演示（T+7:00 ~ 8:00）60 秒
> "评委如果担心 v5.2 的新算法有风险，我演示如何回退到 v1.0 基线行为。
> 
> 第一种：软回退，1 秒生效。"
> 
> [发命令] FUSION,ENABLE,0
> 
> "看，fusion_stage 字段消失了，系统立刻回到 v1.0 的 3 源计数模式。所有 v5.2 新功能（FAR/MID/NEAR/浮点置信度）全部禁用。再发 FUSION,ENABLE,1 立刻恢复。
> 
> 第二种：硬回退，30 秒完整重烧 v1.0 固件：
> git checkout release/v1.0
> pio run -t upload
> 
> 双重保险，绝不影响基线场景。"

### 6.2 现场失败应对剧本

#### 场景 1：雷达没数据（track_active 一直 false）
**症状**：人走过 Dashboard 也没反应
**应对**：
1. 解说"网络延迟，刷新一下"（**别紧张**）
2. 串口查：`echo "RADAR,STATUS" > /dev/tty.usbserial-XXX`
3. 如果 LD2450 输入正常 → 重启 vision_web_server
4. 如果 LD2450 没数据 → 拔插 RX/TX 接线 → 重烧 NodeA
5. **彻底失败**：跳过这部分直接讲算法 + 拿 PNG 证据图

#### 场景 2：视觉黑屏（vision_locked 一直 false）
**症状**：视觉区显示"摄像头未连接"或定格画面
**应对**：
1. 重启 vision_bridge：`python3 tools/vision_bridge_视觉桥接.py --yolo-enabled`
2. 如果重启没用 → 拔插 USB → 换 USB 口
3. 如果换口没用 → 换备用摄像头
4. **彻底失败**：解说"视觉支链异步独立，雷达和 RID 链路继续工作"（演示纯雷达模式）

#### 场景 3：舵机不动
**症状**：SCANNING 不摇头
**应对**：
1. 第一时间检查 5V 电源指示灯 / 测电压
2. 如果电源 OK → 重烧 NodeA（PWM 配置可能丢失）
3. **彻底失败**：解说"算法层不依赖舵机，跟踪逻辑由 Dashboard 显示"

#### 场景 4：NodeB 不发 RID
**症状**：nodeb_online=false 或一直 RID_NONE
**应对**：
1. 检查 NodeB LED 是否在闪（不闪 → 上电问题）
2. 检查 NodeB UART 接 NodeA UART2 是否对（RX/TX 别接反）
3. 用 USB 直接连 NodeB 看串口是否在发
4. **临时方案**：用 host command 注入合作 RID（见 §2.5）

#### 场景 5：Dashboard 不刷新
**症状**：字段定格不变
**应对**：
1. F5 刷浏览器
2. 检查 vision_web_server 是否还在跑（终端有无 traceback）
3. 重启 vision_web_server
4. **临时方案**：直接看串口输出讲解（不依赖 Dashboard）

#### 场景 6：评委要求"现在断电再开机"
**应对**：
1. 关 NodeA + NodeB 电源
2. 等 3 秒
3. 同时上电
4. 解说"启动需要 2-3 秒达到稳态"——舵机回中心、摄像头初始化、传感器握手
5. **缺口**：当前没有启动诊断字段（plan V6 B-3 待修），可能看不出哪个传感器初始化失败

### 6.3 备用演示（5 分钟极简版）

如果时间紧或者主演示崩了，跑这个：

| T | 动作 | 重点 |
|---|---|---|
| 0:00-0:30 | 开场介绍 | 系统拓扑 + 创新点 |
| 0:30-1:30 | 合作目标走入 | RID 自动匹配 / verdict 自动判定 |
| 1:30-3:00 | 非合作目标走入 | EVENT 自动触发 / 抓拍 |
| 3:00-4:00 | 抗干扰（行人） | 算法层不误报 |
| 4:00-5:00 | 软回退演示 + Q&A | 双重保险 |

---

## 7. 自动化矩阵（学生关键疑问：是不是都自动？）

**结论：99% 全自动，1 处半自动。Demo 跑起来后核心检测 / 跟踪 / 抓拍零键盘干预**。

| 行为 | 自动 / 手动 | 关键代码 |
|---|---|---|
| 白名单匹配（RID → 合作判定）| ✅ **全自动** | `main.cpp:639-677 resolveWhitelistDecision()`，毫秒级查表 |
| target_verdict 5 档判定 | ✅ **全自动** | `main.cpp:2110-2147` 每 20ms tick |
| 自动抓拍（AUTO_LOCK / AUTO_HIGH_RISK_ENTER / AUTO_EVENT_OPENED）| ✅ **全自动** | `vision_bridge_视觉桥接.py:1455-1593` 轮询 latest_status.json |
| 事件 open/close 生命周期 | ✅ **全自动** | 风险阈值驱动 `canOpenEventContext()` |
| 舵机扫描 / 跟踪 | ✅ **全自动** | `GimbalController::update()` 自身状态机 |
| 风险等级跃迁 NORMAL→SUSPICIOUS→HIGH_RISK→EVENT | ✅ **全自动** | `HunterAction::update()` 每 tick 比阈值 |
| 多旋翼 4 维分类 | ✅ **全自动** | `TrackManager::updateMultirotorFeatures()` 每帧 |
| FAR/MID/NEAR 切换 | ✅ **全自动** | `Fusion.cpp` 距离驱动 |
| Dashboard 刷新 | ✅ **全自动** | `vision_dashboard.html:4893` setInterval 2000ms |
| NodeB 广播 RID | ⚠️ **半自动** | C3 默认 3s 一次自动广播；可按 `a` 切手动 |

### 你**唯一可能需要按键**的场景

| 场景 | 按什么 | 在哪 |
|---|---|---|
| 演示 v1.0 软回退（评委追问时）| 串口 `FUSION,ENABLE,0` | NodeA 串口 |
| 切换合作 / 非合作目标 | 物理换烧不同 RID 的 C3 板 | 演示桌 |
| 演示 NodeB 离线 | NodeB 串口按 `a` 切自动 OFF | 备用键盘 |
| 演示前 5 分钟启动 3 个 python 脚本 | 命令行运行 | 笔记本 |

**核心 demo 跑起来后**：评委站到画面前 → 系统自己走完一整套（雷达锁定 → 舵机转过去 → 视觉跟踪 → NodeB 自动广播 RID → 白名单自动查表 → verdict 自动写 → 风险自动评分 → 事件自动 open → 抓拍自动触发 → Dashboard 自动 2 秒刷）。**你只解说，不操作。**

---

## 8. 升级候选：UWB DW1000 GNSS-denied 定位

### 8.1 背景

老师指出"低空 GNSS 不可靠 / 缺基准站 / 低轨卫星组网"方向。当前方案是"地面端反无人机感知（防御侧）"，老师希望延伸到"GNSS 失效场景下的低空定位（导航侧）"。

### 8.2 选定方案

DW1000 PA+LNA 模组（深圳硅传科技，¥125/块，3.5-4.5GHz，距离 300m，cm 级精度），4 块（3 锚点 + 1 移动 tag）+ 4 块 ESP32-S3 主控（已有 1 块）。

### 8.3 硬件清单

| 项 | 数量 | 单价 | 小计 |
|---|---:|---:|---:|
| DW1000 PA+LNA 模组 | 4 | ¥125 | ¥500 |
| ESP32-S3 DevKit（补 3 块）| 3 | ¥30-50 | ¥90-150 |
| 杂项 | — | — | ¥30 |
| **合计** | | | **¥620-680** |

### 8.4 测试是否好做

✅ **优势**：室内可测、不依赖外部条件、真值好测（卷尺）、可重复
❌ **难点**：算法门槛（TDoA / TWR + 时钟同步 + 标定 ≥ 2 周）、多锚点同步、标定繁琐、真机难联调（只能手持 tag 模拟）、调参很硬核

**顺利情况**：3 小时 / 一组数据；**不顺利**：1 周才能拿出"演示精度"。

### 8.5 与现有系统的关系

- **互补不冲突**：毫米波 + 视觉负责远距感知（100m / 室外），UWB 负责室内 / 近距精确定位（cm 级）
- **数据流**：UWB 解算 tag 位置 → 当作"合作目标精确位置" → 喂给 Fusion 作第 4 投票源
- **不动主链固件**：UWB 走独立 task + ESP-NOW

### 8.6 工时

≥ 3 周（第 1 周 TWR 联通 / 第 2 周 多锚点 + 求解器 / 第 3 周 标定 + 对接 + demo）。

### 8.7 加上 UWB 后冲击力分析

| 维度 | 加之前 | 加之后 |
|---|---:|---:|
| 创新点数量 | 3 | **4**（+ GNSS denied 定位）|
| 应用场景广度 | 防御侧 | **防御 + 导航**双向 |
| 老师指引覆盖率 | 部分 | **完整** |
| 评委追问应答 | 视觉 / 多旋翼 / 100m | + "GNSS 失效怎么办" |
| 演示新增 | — | +1 段（实时坐标显示，米级精度也行）|
| 风险 | "100m 真无人机数据"被追问 | + "你定位精度多少"（如差则翻车）|

### 8.8 待与老师讨论的决策点

1. 国一答辩日期是哪天？（≥ 3 周才能开工）
2. 是否接受 30-50cm 精度（vs 必须 cm 级 + 长期标定）
3. 经费来源（个人 / 实验室 / 项目）
4. 是否安排队友协作
5. 即使做完，是放主线 demo 还是 PPT 提及

### 8.9 包装话术（创新点 4 候选）

> 雷视融合处理远距（100m）感知，UWB DW1000 负责协同节点间的精确定位（cm 级）。两套技术互补：雷达对小 RCS 目标受限，UWB 解决室内 / GNSS 不可用场景。最终在地面构建"感知 + 定位"双层网络，无需依赖卫星。

---

## 9. 测试前你必须准备的所有东西

### 9.1 硬件清单（演示前一周备齐）

- [ ] NodeA（ESP32-S3）× 1，烧最新 `feat/mac-claude`
- [ ] NodeA 备用 × 1，烧 `release/v1.0`（**前提：tag 要先建**，plan V6 E-1）
- [ ] LD2450 + LD2451 各 1 块
- [ ] NodeB（ESP32-C3）× 1（烧 `SIM-RID-001`）
- [ ] NodeB 备用 × 1（烧 `SIM-RID-999`，演示非合作）
- [ ] USB 摄像头 × 1（+ 备 1）
- [ ] Pan + Tilt 舵机各 1（建议 MG90S 或 MG996R，避免 SG90 力矩不足）
- [ ] 独立 5V/3A 舵机电源 ⚠️ **关键**
- [ ] 三脚架 × 1
- [ ] 笔记本 × 1（+ 备 1）
- [ ] USB Hub 多口
- [ ] DJI Mini 3 × 1（如有）
- [ ] 手机（BLE 仿冒测试 + 录像）
- [ ] 卷尺 / 激光测距（真值距离）
- [ ] 备用电池 / 充电宝

### 9.2 软件清单（上位机预装）

```bash
pip3 install matplotlib opencv-python onnxruntime pyserial flask numpy
```

### 9.3 文档清单（打印随身）

- [ ] **本指南**（`docs/2026-05-25_field_test_complete_guide_v1.md`）
- [ ] **PDF 海报**（`exec_summary_v1.md` 转 PDF，待做，plan V6 E-1）
- [ ] **Q&A 卡片**（`docs/2026-04-30_v5_2_defense_qa_v1.md` 12 项）
- [ ] **5 张 PNG**（`outputs/gimbal_prediction.png` / `fusion_compare_far_mid_near.png` / `multirotor_features.png` / `multirotor_confusion_matrix.png` / `co_sensing_timeline.png`）
- [ ] **demo_submission_runbook**（`docs/2026-05-16_demo_submission_runbook_v1.md`）

---

## 10. 测试流程建议（演示前 1 周）

| 第几天 | 任务 |
|---|---|
| **D-7** | 办公室全功能彩排（跑完 §6 阶段 0-7，记录每个 tab 是否正确） |
| **D-6** | 真机数据采集（按 `field_collection_runbook_v1.md`，DJI Mini 3 × 10/30/50/80/100m × 5 标签） |
| **D-5** | 消融实验（关 LD2451 / NodeB / LD2450 / 视觉 各跑一遍 → 4 张 PNG） |
| **D-4** | v1.0 回退验证（建 `release/v1.0` tag → 烧备用 NodeA → 6 基线零回归） |
| **D-3** | 答辩排练（录屏完整 demo，计时 8-10 分钟，同学扮评委追问 5 大考验） |
| **D-2** | 素材收尾（导 PDF 海报、打印 Q&A 卡、装订成册） |
| **D-1** | 现场踩点 + 应急包准备 |

---

## 11. 5 个评委必命中的现场考验

### 考验 1："拔 NodeB 线试试"
**应反应**：3s 后 `nodeb_online=false` / `rid_status=NONE` / 系统不卡死 / 重连日志开始打印（`NODEB,UART_RESTART,count=N`）
**Q&A**：Q8/Q9（已在 defense_qa_v1.md）

### 考验 2："拔摄像头 USB"
**应反应**：vision_bridge 端报错 / Dashboard 视觉区黑屏 / 雷达 + NodeB 继续工作 / 主链不死
**⚠️ 当前缺口**：Dashboard 没"video_lost"指示（plan V6 F-1 待修）

### 考验 3："手机模拟 BLE 仿冒一个白名单 RID"
**应反应**：NodeB 收到伪造 RID 但**真无人机出现时 RID 不一致** → `rid_status` 跳 SUSPICIOUS 而不是 MATCHED
**当前状态**：未真实装"仿冒检测"，可口头说"设计上看 RSSI + 时序"，引 `RID_SUSPICIOUS` 状态

### 考验 4："现在切回 v1.0 看看"
**应反应**：
- 软回退：`FUSION,ENABLE,0`（1s）
- 硬回退：`git checkout release/v1.0 && pio run -t upload`（30s）
**⚠️ 当前缺口**：`release/v1.0` tag **不存在**（plan V6 E-1 必修！）

### 考验 5："你的能检测多远？我看不到无人机"
**应反应**：拿出 100m 真机测试录像（D-1/D-3 待采）或 `fusion_simulator` 跑 100m 场景实时演示
**⚠️ 当前缺口**：**零真机视频**（plan V6 D-1/D-3 必做）

### 11.1 各考验的详细子问题 + 应答模板

#### 考验 1 子问题展开

**评委可能追问**：
1. **"为什么 3 秒后才显示离线，能不能更快？"**
   > "3 秒是 NodeBConfig::StaleTimeoutMs 配的，设这么长是为了避开 NodeB 偶发心跳丢失误判。如果场景需要更敏感可以调到 1 秒，但会增加误报。"

2. **"NodeB 离线后系统能用吗？"**
   > "可以。看 Dashboard，雷达和视觉链路完全独立，照样能检测目标，只是 target_verdict 不会升到 CONFIRMED_COOPERATIVE_DRONE，会归类为 VISUALLY_CONFIRMED_DRONE 或 PROBABLE_MULTIROTOR。这是降级模式。"

3. **"重连机制是怎么设计的？"**
   > "前 5 次快速重连（每 3 秒一次），如果都失败切到慢速重连（每 15 秒）。看串口可以看到 NODEB,UART_RESTART,count=N 的日志。"

4. **"重连永远不停吗？"**
   > "⚠️ 当前实现是的，没有硬上限。这是 plan 中已记录的 P0.3 待修项，会在下一次迭代加入 MaxTotalReconnectAttempts。"

#### 考验 2 子问题展开

**评委可能追问**：
1. **"摄像头不可用了系统知道吗？"**
   > "vision_locked 字段会变 false，但当前 Dashboard 没有显眼的 'video_lost' 指示。这是已知缺口，下一版会加 camera_online 字段。"

2. **"那评委怎么知道是摄像头坏了还是系统坏了？"**
   > "看串口 - vision_bridge 会打印连接错误。Dashboard 视觉区会显示最后一帧定格。这是用户体验层面的提升项。"

3. **"丢摄像头后多久 fusion 会调整？"**
   > "下次 fusion 评估（最多 100ms），vision_confidence 视为 0，不再加权 0.08 贡献。整个 fusion_confidence 会下降约 8%，但 fusion_stage 不变。"

#### 考验 3 子问题展开

**评委可能追问**：
1. **"如果对手用手机仿冒一个白名单 RID 怎么办？"**
   > "我们设计了三层防御：(1) RID 必须配合活动雷达航迹才能 MATCHED，单纯广播无效；(2) RID_SUSPICIOUS 状态会标记反常的 RID（如 RSSI 突变）；(3) 视觉确认 - 真无人机要有视觉特征。"

2. **"那 SUSPICIOUS 状态是怎么触发的？"**
   > "当 rid_id 短时间内被多个不同来源声称、或 RSSI 与历史不一致时触发。当前是设计预留，完整规则要看 RidConfig::SuspiciousWindowMs。"

3. **"实际防住了吗？测过吗？"**
   > "⚠️ 老实说，仿冒检测当前还是设计阶段，没做现场对抗测试。这是 v5.3 的工作，依赖 NodeB 升级到真 Wi-Fi/BLE 监听。"

#### 考验 4 子问题展开

**评委可能追问**：
1. **"v1.0 行为有什么不同？"**
   > "v1.0 用 3 源计数（雷达 + 视觉 + RID 各 1 票），简单累加；v5.2 用距离/速度一致性矩阵 + 浮点置信度 + FAR/MID/NEAR 分阶段。v5.2 更精确但更复杂。"

2. **"软回退和硬回退区别？"**
   > "软回退（FUSION,ENABLE,0）只关 v5.2 融合算法，其他新功能（target_verdict、多旋翼、舵机预测）继续运行。硬回退（git checkout release/v1.0）整套固件回到 v1.0 时刻。"

3. **"软回退能演示完整 v1.0 行为吗？"**
   > "不能 100%。只回退了融合层。如果要严格 v1.0 行为，必须硬回退。"

4. **"release/v1.0 真的烧得起来吗？"**
   > "⚠️ 这是当前缺口，tag 还没建。plan 中 E-1 项必修。"

#### 考验 5 子问题展开

**评委可能追问**：
1. **"100m 实际能测到吗？"**
   > "100m 是 LD2451 标称距离，对人或车这种大目标够。但对 DJI Mini 3 这种小型多旋翼，RCS 只有 0.01 m²，实测有效距离可能只有 30-50m。100m 检测主要靠**视觉**+**长焦摄像头**+ NodeB RID。"

2. **"用真无人机测过吗？"**
   > "⚠️ 当前测试数据是合成 + 仿真。真无人机现场测试还没做，是 plan 中 D-1 必做项。"

3. **"为什么不直接用更强的雷达？"**
   > "成本和功耗。我们用 LD2451（百元级）+ 视觉 + 协同节点的组合方案，整套方案成本控制在千元内，远低于专用反无人机雷达。这是边缘部署的核心定位。"

4. **"那你的优势在哪？"**
   > "(1) 多模态融合避免单源失效；(2) 算法层抗干扰过滤非无人机；(3) 边缘节点 + 协同感知，不依赖中心化决策；(4) GNSS denied 场景的被动感知（如果做了 UWB）。"

### 11.2 评委高频问题速查表

| 评委问 | 30 秒回答 | 文档链接 |
|---|---|---|
| 能检测多远？ | 5-100m，分 FAR/MID/NEAR 三阶段 | algorithm_formula_book §3 |
| 怎么识别合作目标？ | RID 匹配 + 白名单允许 + 命中位 = 1 | 本指南 §2 |
| 怎么过滤行人/车/鸟？ | 多旋翼 4 维特征：速度区间 + 持续时长 + 悬停容忍 + 轨迹曲率 | algorithm_formula_book §5 |
| 视觉雾天怎么办？ | vision_confidence 自动降级，雷达主导 | defense_qa Q10 |
| 视觉真在检测吗？ | Dashboard 绿框 = CSRT 实时跟踪，红框 = YOLO 每 10 帧验证 | exec_summary §3 |
| ESP32 是不是噱头？ | NodeA 主控 + NodeB 协同，UART 双节点边缘部署，非云端化 | exec_summary §1 |
| 怎么回退到 v1.0？ | 软：FUSION,ENABLE,0（1s）；硬：git checkout（30s） | runbook §6 |
| 多旋翼 5 帧是怎么定的？ | 经验权衡：3 帧 FP=12%，5 帧 FP=3%，7 帧不再下降但延迟 0.7s | defense_qa Q12 |
| 100m 真测过吗？ | ⚠️ 真机数据待采（plan D-1） | — |
| NodeB 不发 RID 怎么办？ | rid_status=NONE，系统降级为视觉 + 雷达模式 | defense_qa Q9 |
| 仿冒 RID 怎么防？ | 设计三层防御，对抗测试待做（v5.3） | 本指南 §11.1 考验 3 |
| 端云怎么分工？ | 端侧采集 + 算法，云端只接告警 + 证据，离线可用 | exec_summary §2 |

---

## 12. 现场最大风险（按概率 × 严重度）

| 风险 | 概率 | 缓解 |
|---|---|---|
| 摄像头 USB 接触不良 | 高 | 带备用 USB 线 + 备用摄像头 |
| 笔记本死机 | 中 | 备用笔记本 |
| 雷达干扰（金属反射）| 中 | 提前踩点测试场地 |
| 演示流程忘词 | 中 | 打印 SOP 放手边 |
| **`release/v1.0` tag 不存在评委追问** | **高** | **plan V6 E-1 必修** |
| **零真无人机视频被追问 100m** | **高** | **plan V6 D-1/D-3 必做** |
| 现场 Wi-Fi 噪声干扰 BLE | 低 | NodeB 走 UART 不依赖 Wi-Fi |
| 舵机不动 / 抖动 | 中 | 独立 5V/3A 电源 + 备用舵机 |

---

## 13. 现在最该做的 3 件事

1. **建 `release/v1.0` tag + 验证回退**（1 小时，不做现场必翻车）
2. **去采集 DJI Mini 3 真机数据**（1 天，国一必命中考验）
3. **办公室跑一次完整 §6 彩排**（半天，发现剧本 bug）

---

## 14. 给小白的解释

**这是什么**：把"演示当天要做什么、各硬件什么状态、评委会问什么"打包成一份现场可翻的手册。

**有什么用**：演示前一晚把这份打印出来贴桌上；现场遇到任何问题先翻这份；评委追问"你这个是不是手动的"直接翻 §7 给他看。

**你现在该怎么做**：
1. 通读一遍找疑问
2. 标出对应的代码 / 文档链接看明白
3. 按 §10 准备演示日程
4. 把 §11 五大考验背熟
5. UWB 升级先和老师讨论（§8.8 5 个问题）再决定是否开工

---

## 15. 演示前 30 分钟启动 SOP（每个命令什么时候敲）

### T-30:00 ~ T-25:00 — 硬件上电
```
1. 摆好三脚架，固定云台
2. 接好舵机独立 5V 电源（先别开关）
3. 接 NodeA USB 到笔记本
4. 接 NodeB USB 到笔记本（或 NodeA UART2）
5. 接摄像头 USB 到笔记本
6. 开舵机电源
7. 给 NodeA 上电 → 听舵机回中心声音
8. 给 NodeB 上电 → 看 LED 是否闪
```

### T-25:00 ~ T-20:00 — 启动笔记本软件
```bash
# 终端 1：启动 NodeA 串口桥接
cd ~/Projects/Flytotal
python3 tools/node_a_serial_bridge_NodeA串口桥接.py \
  --port /dev/tty.usbserial-NODEA \
  --baud 115200

# 应看到：
#   [BRIDGE] Connected to /dev/tty.usbserial-NODEA
#   [NODEA] HB,now=1234,risk=NORMAL,...
```

### T-20:00 ~ T-15:00 — 启动视觉桥接
```bash
# 终端 2：启动 vision_bridge（带 YOLO）
python3 tools/vision_bridge_视觉桥接.py --yolo-enabled

# 应看到：
#   [VISION] Camera 0 opened, resolution 1280x720
#   [VISION] YOLO model loaded: models/yolov8n.onnx
#   [VISION] Tracker initialized: CSRT
#   [VISION] Frame rate: 30 FPS
```

### T-15:00 ~ T-10:00 — 启动 Web 服务
```bash
# 终端 3：启动 vision_web_server
python3 tools/vision_web_server_视觉网页服务.py \
  --port 8765

# 应看到：
#   [WEB] Listening on http://127.0.0.1:8765
#   [WEB] Loaded latest_status.json
```

### T-10:00 ~ T-05:00 — 浏览器验证
```
1. 浏览器打开 http://localhost:8765
2. 检查 8 个 tab 全部能切换：
   ✓ 视觉
   ✓ 捕获  
   ✓ 节点状态
   ✓ 事件
   ✓ 测试
   ✓ 证据
   ✓ 交付
   ✓ 协同感知
3. 视觉区有图像，看见自己
4. 节点状态卡片全绿
5. 自动刷新工作（2 秒一刷，看 timestamp_ms 字段变化）
```

### T-05:00 ~ T-00:00 — 功能预检
```
1. 你走到摄像头前 → 视觉区出现绿框 + 红框 → vision_locked=true
2. 同学 1 拿 NodeB 走过 → rid_status 应跳 MATCHED
3. 同学 1 走开 → rid_status 5 秒内回 NONE
4. 故意拔 NodeB USB → 3 秒后 nodeb_online=false
5. 重接 NodeB → 自动重连，nodeb_online=true
```

如任一步失败 → 立刻按 §6.2 排查；不行就走 §6.3 极简版。

---

## 16. Dashboard 字段对照表（评委追问时秒查）

### 节点状态卡片

| 字段 | 含义 | 正常值 | 异常处理 |
|---|---|---|---|
| `node_id` | 节点 ID | "A1" | — |
| `node_role` | 节点角色 | "EDGE" | — |
| `risk_level` | 风险等级 | NORMAL | 升级 = 检测到威胁 |
| `target_verdict` | 目标判定 | UNKNOWN | 见 §2.3 |
| `track_active` | 雷达航迹活动 | true/false | — |
| `track_confirmed` | 航迹确认（≥5 帧）| true/false | — |
| `event_active` | 事件激活 | 0/1 | 1 = 触发告警 |
| `nodeb_online` | NodeB 在线 | true | false 3s = 真断线 |

### RID 卡片

| 字段 | 含义 | 状态值 |
|---|---|---|
| `rid_id` | RID 标识 | "SIM-RID-001" 等 |
| `rid_device_type` | 设备类型 | UAV / RC / BLE |
| `rid_source` | 来源 | NODE_B / USB |
| `rid_status` | RID 状态机 | NONE / RECEIVED / MATCHED / EXPIRED / INVALID |
| `wl_status` | 白名单状态 | WL_UNKNOWN / WL_ALLOWED / WL_DENIED / WL_EXPIRED |
| `rid_whitelist_hit` | 命中位 | 0/1 |
| `rid_signal_strength` | RSSI | -50 ~ -80 dBm |
| `rid_auth_status` | 鉴权状态 | VALID / INVALID / UNKNOWN |

### 雷达卡片

| 字段 | 含义 | 单位 |
|---|---|---|
| `radar_track.x_mm` | 横向位置 | mm |
| `radar_track.y_mm` | 纵向距离 | mm |
| `radar_track.vx_mm_s` | 横向速度 | mm/s |
| `radar_track.vy_mm_s` | 纵向速度 | mm/s |
| `radar_track.seen_count` | 累计帧数 | — |
| `radar_track.is_multirotor_like` | 多旋翼标志 | true/false |
| `radar_track.multirotor_score` | 多旋翼评分 | 0-100 |
| `ld2451_valid` | LD2451 有效 | true/false |
| `lr_range_m` | LD2451 距离 | m |
| `lr_speed_mps` | LD2451 速度 | m/s |
| `far_motion_trigger` | 远距运动触发 | true/false |

### 视觉卡片

| 字段 | 含义 | 取值 |
|---|---|---|
| `vision_state` | 视觉状态 | IDLE / SEARCHING / LOCKED / LOST |
| `vision_locked` | 视觉锁定 | true/false |
| `vision_confidence` | 置信度 | 0.0-1.0（≥0.7 算可信） |
| `bbox_stability_score` | 框稳定度 | 0.0-1.0（≥0.6 算稳） |
| `tracker_state` | 跟踪器状态 | TRACKING / OCCLUDED / LOST |
| `vision_quality` | 环境质量 | CLEAR / LOW_LIGHT / FOG_OR_BLUR |

### 融合卡片

| 字段 | 含义 | 取值 |
|---|---|---|
| `fusion_stage` | 分阶段 | FAR / MID / NEAR / NONE |
| `fusion_level` | 融合等级 | NONE / LOW / MID / HIGH |
| `fusion_confidence` | 浮点置信度 | 0.0-1.0 |
| `fusion_reason` | 融合理由文本 | "RID+RADAR+VISION agreement" 等 |
| `fusion_enabled` | v5.2 是否启用 | true/false（false = v1.0 兼容模式） |

### 事件卡片

| 字段 | 含义 |
|---|---|
| `event_id` | 事件 ID（格式 NodeId-时间戳-序号）|
| `event_state` | EVENT_STATE_NONE / OPEN / CLOSED |
| `start_time_ms` | 事件开始时间 |
| `close_time_ms` | 事件关闭时间 |
| `close_reason` | 关闭原因 |
| `capture_path` | 抓拍 JPEG 路径 |
| `risk_score` | 触发事件时的风险评分 |
| `trigger_flags` | 触发位掩码 |

### 协同卡片

| 字段 | 含义 |
|---|---|
| `nodeb_node_id` | NodeB 节点 ID |
| `nodeb_status` | OFFLINE / ONLINE / OFFLINE_OR_TIMEOUT |
| `nodeb_rssi` | NodeB 信号强度 |
| `handoff_from` | handoff 起点节点 |
| `handoff_to` | handoff 终点节点 |
| `continuity_hint` | SINGLE_NODE / HANDOFF_PENDING / HANDOFF_ACTIVE / HANDOVER_DONE |
| `prev_node_id` | 前一节点 |

---

## 17. 现场快速参考卡（打印 A4 单页贴桌前）

```
═══════════════════════════════════════════════════════════
  FLYTOTAL 现场快速参考卡 · 演示日必带
═══════════════════════════════════════════════════════════

【硬件状态自检】
NodeA LED 常亮  · LD2450 常亮  · LD2451 常亮
NodeB LED 1Hz 闪  · 摄像头 LED 亮 · 舵机回中心 90°/90°
Dashboard 8 tab 全绿 · 自动刷 2s

【关键命令】
回退 v5.2:        FUSION,ENABLE,0  → FUSION,ENABLE,1
查状态:           FUSION,STATUS  · RID,STATUS
注入合作 RID:     RID,MSG,SIM-RID-001,UAV,USB,...,VALID,WL_OK,-50
注入非合作 RID:   RID,MSG,SIM-RID-999,UAV,USB,...,VALID,WL_OK,-50

【5 档判定】
🟢 CONFIRMED_COOPERATIVE_DRONE = RID 匹配 + 白名单
🔴 VISUALLY_CONFIRMED_DRONE    = 视觉锁定 + 雷达
🟡 PROBABLE_MULTIROTOR        = 多旋翼特征评分 ≥65
🟡 MOTION_ALERT               = LD2451 远距运动
⚪ UNKNOWN_TARGET             = 都不满足

【舵机状态】
SCANNING   = 左右摇头 ±15°
ACQUIRING  = 转向目标
TRACKING   = 平滑跟踪（180ms 提前量）
LOST       = 保持 3s 后回 SCANNING

【NodeB 控制】
按 a   = 切自动 / 手动 广播
按 r   = 手动发一条 RID
按 h   = 手动发心跳

【白名单 RID】
SIM-RID-001  → 合作（绿）
SIM-RID-999  → 非合作（红）
SIM-RID-EXPIRED → 过期（黄）
其他 → UNKNOWN（灰）

【失败应对】
雷达没数据 → RADAR,STATUS / 拔插 / 重烧
视觉黑屏 → 重启 vision_bridge / 换摄像头 / 解说降级
舵机不动 → 检 5V 电源 / GPIO 4/5 / 重烧
NodeB 离线 → 看 LED / 拔插 UART / host 注入 RID 替代

【绝对不能慌】
1. 网络延迟，刷新一下          ← 万能开场
2. 这是预期降级，看 ...          ← 出问题转优势
3. 我演示软回退给您看           ← 不会的就回退
═══════════════════════════════════════════════════════════
```

---

## 18. 附录：所有相关代码 / 文档索引

### 代码（按主题）

| 主题 | 文件:行号 |
|---|---|
| 白名单表 | src/main.cpp:503-508 |
| RID 解析 | src/main.cpp:679-707 |
| 白名单查表 | src/main.cpp:639-677 |
| RID 状态机 | src/main.cpp:765-799 |
| target_verdict 判定 | src/main.cpp:2110-2147 |
| 舵机控制器 | lib/GimbalController/GimbalController.cpp |
| 云台预测器 | lib/GimbalPredictor/GimbalPredictor.cpp |
| 多旋翼分类 | lib/TrackManager/TrackManager.cpp:54-106 |
| 融合算法 | lib/Fusion/Fusion.cpp |
| Hunter 风险评分 | lib/HunterAction/HunterAction.cpp |
| LD2450 解析 | lib/RadarParser/RadarParser.cpp |
| LD2451 解析 | lib/Ld2451Parser/Ld2451Parser.cpp |
| 阈值配置 | include/AppConfig.h |
| 共享数据结构 | include/SharedData.h |
| NodeB 固件 | examples/nodeb_c3_identity_uart/src/main.cpp |
| Dashboard | tools/vision_dashboard.html |
| 视觉桥接 | tools/vision_bridge_视觉桥接.py |
| Web 服务 | tools/vision_web_server_视觉网页服务.py |
| 串口桥接 | tools/node_a_serial_bridge_NodeA串口桥接.py |

### 文档（按主题）

| 主题 | 文件 |
|---|---|
| **本指南** | docs/2026-05-25_field_test_complete_guide_v1.md |
| 答辩 Q&A 12 项 | docs/2026-04-30_v5_2_defense_qa_v1.md |
| 一页执行摘要 | docs/2026-05-09_exec_summary_v1.md |
| 端到端延迟预算 | docs/2026-05-09_latency_budget_v1.md |
| v5.2 总纲 | docs/2026-05-08_v5_2_overall_upgrade_v1.md |
| 算法公式书 | docs/2026-05-08_algorithm_formula_book_v1.md |
| 硬件 BOM | docs/2026-05-08_hardware_bom_wiring_v1.md |
| 编译 / 烧录 / 跑通 | docs/2026-05-08_v5_2_runbook_v1.md |
| Changelog v5.2 | docs/CHANGELOG_v5.2.md |
| 真摄像头验收 | docs/2026-05-16_real_camera_acceptance_record_v1.md |
| 现场采集 runbook | docs/2026-05-16_field_collection_runbook_v1.md |
| 答辩日 SOP | docs/2026-05-16_demo_submission_runbook_v1.md |
| Demo 基线 | docs/2026-05-12_demo_acceptance_record_v1.md |
| 算法证据索引 | docs/algorithm_evidence/README.md |

### Plan 文档（路线图）

| 路径 | 内容 |
|---|---|
| `~/.claude/plans/ld2451-c3-100m-esp32-distributed-koala.md` | V6 plan：A-1~A-5 修完后剩余 17 项缺口 + UWB 升级候选 |

### 产物（outputs/，本地，不入 git）

| 文件 | 内容 |
|---|---|
| `outputs/gimbal_prediction.png` | 云台预测对比曲线（lead_time 0/0.12/0.18s）|
| `outputs/fusion_compare_far_mid_near.png` | 融合新旧算法对比 |
| `outputs/multirotor_features.png` | 多旋翼 4 维特征分布 |
| `outputs/multirotor_confusion_matrix.png` | 多旋翼分类混淆矩阵 |
| `outputs/co_sensing_timeline.png` | 协同感知状态切换时序 |
