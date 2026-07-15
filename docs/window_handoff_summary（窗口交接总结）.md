# Context from my IDE setup

## 2026-04-13 ~ 2026-04-14 最新优先交接（新聊天先读这段）

这段是当前最高优先级交接，优先于后文历史记录。

### 1. 本轮计划完成度（按用户 4.13/4.14 口径）

#### 2026-04-13（硬件收口日）
已完成并落盘：
1. 《硬件测试问题清单》  
   - `docs/2026-04-13_hardware_issue_list_v1.1（硬件测试问题清单）.md`
2. 《接线/供电/端口表》  
   - `docs/2026-04-13_wiring_power_port_table_v1.1（接线供电端口表V1.1）.md`
3. 《可运行参数表 V1.1》  
   - `docs/2026-04-13_runtime_parameter_table_v1.1（可运行参数表V1.1）.md`
4. 《Node A Base Demo V1.1 说明》  
   - `docs/2026-04-13_node_a_base_demo_v1.1（NodeA基线说明V1.1）.md`
5. 当日更新记录  
   - `docs/2026-04-13_node_a_feature_updates（NodeA功能更新）.md`

#### 2026-04-14（身份链接入主链）
已完成并落盘：
1. RID 数据结构/状态定义/匹配规则文档已完成。  
2. 固件主链已接入 `RID,MSG` + 超时窗口 + 白名单判定。  
3. 网页已可显示 `rid_status / rid_whitelist_hit / rid_last_update_ms`。  
4. 当日更新记录：  
   - `docs/2026-04-14_node_a_feature_updates（NodeA功能更新）.md`

### 2. 关键代码落地（必须记住）

1. RID 新状态主口径：`NONE / RECEIVED / MATCHED / EXPIRED / INVALID`（旧别名仍兼容）。
2. `track_injector` 已加预检门禁：
   - 运行 suite 前会检查 `STATUS` + `RID,STATUS`
   - 强校验 `baseline_version=Node_A_Base_Demo_V1.1`
   - 不通过默认阻断，可用 `--allow-baseline-mismatch` 临时放行
3. 已修复实机崩溃：
   - `STATUS` 触发 `Track_Task` 栈溢出
   - 修复方式：`Track_Task` 栈 `6144 -> 12288`（`src/main.cpp`）

### 3. 本轮实机验收事实（已通过）

1. 命令：  
   `python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --boot-wait 8`
2. 结果：  
   - 预检通过：`ok=1`
   - 套件通过：`passed=6, failed=0`
3. 状态链路符合新口径：
   - `RID,MISSING -> rid_status=NONE`
   - `RID,OK -> rid_status=MATCHED`
   - `RID,SUSPICIOUS -> rid_status=INVALID`

### 4. 新增但尚未实机执行的套件（下一窗口第一优先）

已新增：`rid_identity_chain_v1`（验证 `RID,MSG` 主链三场景）
1. `VALID + WL_OK -> MATCHED`
2. 超时 -> `EXPIRED`
3. `INVALID + DENY -> INVALID`

执行命令：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite rid_identity_chain_v1 --boot-wait 8
```
预期：`Suite summary: passed=3, failed=0`

### 5. 新聊天开工固定模板（必须遵守）

用户说“继续推进”时，助手必须先给：
1. 本轮计划（3-6条）
2. 每条状态（`DONE/DOING/TODO`）
3. 计划位置、目标文件、变更内容、目的、影响、验收方式
4. 最后一行固定问句：`是否现在开始改代码？`

### 6. 下一窗口建议执行顺序（直接照做）

1. 跑 `rid_identity_chain_v1` 并拿实机结果。  
2. 若通过，把 PASS 证据补入：
   - `docs/2026-04-14_rid_log_samples_v1（身份链日志样例V1）.md`
   - `docs/2026-04-14_node_a_feature_updates（NodeA功能更新）.md`
3. 再回归跑一次：`risk_event_vision_chain_v1`，确认无回退。  
4. 两个套件都 PASS 后，再进入下一日期计划项（不在同一小点反复打磨）。

### 7. 给下一窗口的最短结论

当前系统已达到：
1. `Node_A_Base_Demo_V1.1` 基线稳定可跑。
2. 4.13 收口交付齐全。
3. 4.14 身份主链已接入并完成主套件实机通过。
4. 下一步是补齐 `RID,MSG` 专项套件的实机闭环证据，不要回到旧问题反复打磨。

## 4.13-4.14 原始计划（强约束版，后续会话必须按此推进）

下面是用户明确要求的计划口径，后续新会话“继续推进”必须以这两天计划为第一约束，不得私自改阶段目标。

### 2026-04-13（周一）
主题：硬件测试结果收口 + Node A 基线冻结 + 问题清零

当天原则：
1. 不加新功能，只做收口。
2. 把硬件测试暴露问题分三类管理：
   - 必须当天解决
   - 本周内必须解决
   - 本周明确不做

必须完成的交付：
1. 《硬件测试问题清单》
   - 每条包含：现象、触发条件、是否稳定复现、影响范围、优先级、计划修复日。
2. 《可运行参数表 V1.1》
   - 至少包含：`ConfirmFrames`、`LostTimeoutMs`、风险阈值、云台扫描步进、跟踪平滑参数、事件触发阈值、抓拍触发条件、`Uplink` 发送频率。
3. 《接线图/供电图/端口表》
   - 必须写死：模块端口映射、共地关系、舵机是否独立供电、USB 摄像头连接、串口号和波特率。
4. 版本冻结
   - 当天基线版本名：`Node A Base Demo V1.1`。
5. 闭环复测（至少两场景）
   - 正常目标：进入 -> 跟踪 -> 离开
   - 高风险目标：进入 -> 告警 -> 事件生成 -> 网页显示

当天结束必须拿到：
1. 《硬件测试问题清单》
2. 《接线/供电/端口表》
3. 《可运行参数表 V1.1》
4. 《Node A Base Demo V1.1 说明》

### 2026-04-14（周二）
主题：身份接收链接入主链

当天目标：
1. 让系统从“只发现目标”升级为“可做初步合法性判断”。
2. 重点是打通测试身份链闭环，不追求复杂协议。

必须完成的内容：
1. 定义 RID / 测试身份数据结构
   - 至少包含：`rid_id`、`device_type`、`source`、`timestamp`、`auth_status`、`whitelist_tag`、`signal_strength`（可选）。
2. 固定 RID 状态定义
   - `RID_NONE`、`RID_RECEIVED`、`RID_MATCHED`、`RID_EXPIRED`、`RID_INVALID`。
3. 打通身份接收链
   - Node B 可用则用 Node B 周期广播；否则用临时 ESP32/脚本模拟；关键是 Node A 必须可接收。
4. 建立轨迹-身份关联逻辑
   - 只有“有轨迹 + 时间窗内收到身份 + 白名单通过”才判合法。
5. 把身份接入 Hunter 状态机
   - 有轨迹 + 无身份 -> 可疑链
   - 有轨迹 + 身份白名单通过 -> `RID_MATCHED` / 低风险链
   - 异常身份/非白名单 -> 保持可疑或升风险
   - 身份超时丢失 -> 不能瞬时跳事件，需要缓冲机制
6. 网页端同步展示
   - `rid_status`
   - 白名单命中
   - 最近身份更新时间

当天不能漏的细节：
1. 身份接收必须有超时机制。
2. 身份匹配必须有时间窗口，不能“一次通过永久合法”。

当天结束必须拿到：
1. 《RID 数据结构定义》
2. 《RID 状态定义》
3. 《轨迹-身份匹配规则》
4. 身份正常/缺失/异常三组日志样例
5. 网页端 `rid_status` 展示成功

## 执行纪律（新会话继续推进时强制生效）

1. 每次“继续推进”先给：
   - 本轮计划（3-6条）
   - 状态标记（`DONE/DOING/TODO`）
2. 每次改代码前必须先写：
   - 计划位置、目标文件、变更内容、目的、影响、验收方式
3. 每次改代码前必须问：
   - `是否现在开始改代码？`
4. 当前点达到“可用”后，必须切到计划中的下一个缺口，不在同一点反复打磨。

## Active file
- `docs/2026-04-02_window_handoff_summary（窗口交接总结）.md`

## Open tabs
- `src/main.cpp`
- `docs/2026-04-02_window_handoff_summary（窗口交接总结）.md`
- `docs/10serial_command_quick_reference（串口命令速查表）.md`
- `tools/track_injector_轨迹注入器.py`
- `platformio.ini`

## 当前项目背景
这是 `Flytotal` 的 `PlatformIO/ESP32-S3` 工程。  
当前主线仍然是：
- `Node A + 雷达 + 云台` 单节点闭环

并在这条主线之上继续推进：
- 风险分级可运行、可解释
- 事件对象结构化
- 串口输出统一
- 联调流程标准化
- 后续接入 `USB` 摄像头做视觉链

当前已经不是“先跑起来”的阶段，而是：
- 主链已闭环
- 风险和事件语义已基本成型
- 需要把测试流程、操作体验、后续视觉接入做顺

## 用户已明确的协作要求（必须严格遵守）
1. 必须按用户给出的日期计划推进，不私自做阶段映射。  
2. 每次改代码前先说明：
   - 计划位置
   - 目标文件
   - 变更内容
   - 目的
   - 影响
   - 验收方式
3. 改代码前必须再问一句：`是否现在开始改代码？`
4. 解释必须“详细 + 通俗”，不能只堆术语。
5. 如果用户说“继续推进”，含义是：
   - 如果当前点已够用，就进入计划里的下一个相关功能
   - 不要一直围着一个很小的点反复转
6. 优先推进代码功能，不要发散做大量无关文档。
7. 每天新增内容写进“日期开头”的功能更新文档。
8. 当前主链已较大，新增功能尽量低风险、增量式推进。
9. 每轮推进前先对齐用户计划清单，不要长期停留在同一个功能模块反复打磨；当前点达到“可用”后，立即切到计划中的下一个缺口项。
10. 每次用户说“继续推进”时，必须先给“本轮计划（3-6 条）+ 当前状态（DONE/DOING/TODO）”，再开始执行与改动；计划直接在回复里给，不新增独立计划文档。

## 历史已稳定基础（已验证通过）
- 舵机手动测试、安全模式、诊断模式正常
- 模拟轨迹链路正常
- 真实雷达链路正常
- 主链 `TrackManager -> HunterAction -> GimbalController -> UPLINK` 已跑通
- `SUMMARY`、`HANDOVER`、`LASTEVENT` 等骨架均已接入
- 单节点 `Node A + 雷达 + 云台` 已达到：
  - 可联调
  - 可演示
  - 可继续集成

## 本窗口已落地的重要代码能力

### 1. 风险规则与事件对象主链已成型
已具备：
- 风险分数分项输出
- 风险状态升级 / 保持 / 回落
- 事件对象 `OPEN / CLOSED`
- 统一关闭原因字段

已统一的关键风险分项：
- `risk_base`
- `risk_persistence`
- `risk_confirmed`
- `risk_rid`
- `risk_proximity`
- `risk_motion`

已统一的关键关闭原因：
- `RISK_DOWNGRADE`
- `TRACK_LOST`
- `RESET`

### 2. 4.7 核心验收结果
这一窗口里，`4.7` 的核心功能已经通过，不要再把它当“没完成”。

已经实际验到：
- 连续模拟轨迹可进入 `track_active=1`
- 连续确认后可进入 `track_confirmed=1`
- `RID,MISSING` 时风险升高，事件对象打开
- `RID,OK` 后风险可回落
- `current_event_close_reason=RISK_DOWNGRADE` 已正确出现
- `TRACK,CLEAR` 后 `current_event_close_reason=TRACK_LOST` 已正确出现

也就是说，真正重要的“事件对象关闭语义”已经打通。

### 3. 4.7 剩余已知问题
还有一个尾巴没有完全打磨干净：

- `LASTEVENT` 最近事件缓存不够稳定
- 在某些关闭路径下仍然会出现：
  - `LASTEVENT,NONE`
  - 或被普通状态如 `HUNTER_STATE` 覆盖

当前结论：
- 这是“最近事件缓存层”的问题
- 不是主链问题
- 不是风险评分问题
- 不是事件对象问题

处理策略已经确定：
- **不要再在 4.7 上继续耗太久**
- 可以带着这个已知问题进入 `4.8`
- 后面如果云端留痕/日志中心阶段还需要，再单独重构 `LASTEVENT`

### 4. 新增串口短输出能力
为了解决“命令记不住、输出太长看不懂”，本窗口新增：

- `BRIEF`

作用：
- 一条短输出看核心状态

重点字段：
- `main`
- `track`
- `active`
- `confirmed`
- `hunter`
- `gimbal`
- `rid`
- `risk`
- `risk_level`
- `event_active`
- `event_id`
- `event_state`
- `event_close_reason`
- `x / y`

这条命令已经接入：
- `src/main.cpp`

### 5. `HELP` 已按分组重排
现在 `HELP` 不再是一坨平铺命令，而是按下面几组显示：
- `Common`
- `Simulation`
- `Debug`
- `Servo`
- `Reset`

这样后续现场联调时，不再需要靠记忆回想命令。

### 6. 串口速查表已建立
已新增：
- `docs/10serial_command_quick_reference（串口命令速查表）.md`

用途：
- 帮助用户快速找常用命令
- 说明哪些命令适合手工点查
- 说明哪些流程应交给脚本

注意：
- 这个文档当前存在编码/显示异常风险
- 下个窗口如果要继续整理文档，优先先把它转成稳定 UTF-8 中文内容

### 7. `4.7` 脚本化验收方式已建立
为了避免手工串口输入受 1.5 秒轨迹窗口影响，已确定：

不要再用人手连敲串口完成 `4.7` 验收。

统一用脚本：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --validate-47
```

这条脚本会自动执行：
- `RESET`
- `DEBUG,OFF`
- `UPLINK,OFF`
- 连续 `TRACK`
- `RID` 切换
- `RISK,STATUS`
- `EVENT,STATUS`
- 回落验证
- 丢失验证
- 复位验证

### 8. 工具链与视觉侧现状
当前项目里已存在并可继续用的工具链：
- `tools/track_injector_轨迹注入器.py`
- `tools/node_a_serial_bridge_NodeA串口桥接.py`
- `tools/vision_bridge_视觉桥接.py`
- `tools/vision_web_server_视觉网页服务.py`
- `tools/vision_dashboard.html`

其中本窗口最重要的新增现实条件是：
- **USB 摄像头已经到货**

这意味着下个阶段可以正式推进：
- PC 侧摄像头画面
- OpenCV 跟踪
- 视觉锁定
- 抓拍链验证

但注意：
- 当前窗口并没有开始做 USB 摄像头接入代码改动
- 只是确认硬件条件已经具备

## 当前最推荐的手工串口用法
以后手工串口先用下面这组：

```text
HELP
DEBUG,OFF
UPLINK,OFF
BRIEF
RISK,STATUS
EVENT,STATUS
```

如果只是快速看状态：
- 先看 `BRIEF`

如果要看风险：
- 再查 `RISK,STATUS`

如果要看事件：
- 再查 `EVENT,STATUS`

不要一上来就盯最长的输出行。

## 编译状态
- 本窗口内多次执行 `platformio run`
- 主工程编译通过
- 最近一次通过时间：`2026-04-06`

当前可用命令：
```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run
```

说明：
- 机器上 `PlatformIO` 本身可用
- 只是系统 `PATH` 里未必有 `platformio / pio`
- 直接走上面这条最稳

## 环境与仓库状态
- 工作目录：`c:\Users\WZwai\Documents\PlatformIO\Projects\Flytotal`
- 非标准 git 仓库
- `git diff --name-only` 会提示 `Not a git repository`
- 不依赖 git 流程查看改动

## 计划映射结论（按用户计划口径）
- `2026-04-06`：主链边界冻结、状态定义统一、字段统一、日志清理
  - 已完成主体
- `2026-04-07`：风险分级规则、保持/回落、事件对象、关闭语义
  - 已完成核心功能
  - `LASTEVENT` 仍有已知尾巴，但不建议继续在这一步耗
- 下一步应进入：`2026-04-08`
  - 标准化测试流程
  - 场景化测试方式
  - 更清晰的操作/验收体验

## 周额度更新时间（固定口径）
- 当前 4.9 周期的下一次周计划窗口建议更新时间：`2026-04-13（周一）`。
- 若 `2026-04-09 ~ 2026-04-12` 期间出现阻塞级问题（主链回退、字段映射失真、套件连续失败），可提前做一次临时周额度更新。

## 下个窗口建议优先做什么
最推荐顺序：

### 方案 A：正式进入 4.8
先做“标准测试流程和场景模板”，重点不是再修主链，而是：
- 哪些测试要跑
- 每个测试看哪些字段
- 怎样快速判断通过/失败

### 方案 B：开始最小 USB 摄像头联调准备
因为 USB 摄像头已经到货，下个窗口可以先做：
- 摄像头识别
- `vision_bridge_视觉桥接.py` 画面跑通
- 手动选框、视觉锁定、抓拍最小验证

注意：
- 这一步应算 `4.8 -> 4.9` 的准备
- 先从 PC 侧单独跑通，不要一上来就和固件主链混改

### 方案 C：只做低风险操作性增强
如果不想马上上视觉，也可以继续做：
- 更短的状态命令
- 更清晰的测试输出
- 更顺手的脚本提示

## 下个窗口开工模板（固定先发）
下个窗口继续协作时，先按这个模板发：

1. 计划位置  
2. 目标文件  
3. 变更内容  
4. 目的  
5. 影响  
6. 验收方式  

最后统一一句：
`是否现在开始改代码？`

## 最后结论
这个窗口最重要的真实结论不是“还有一个小尾巴没修完”，而是：

- `4.7` 主目标已经完成
- 风险升级、回落、关闭原因本体已经成立
- 串口可操作性已经开始补强
- USB 摄像头已经到位，可以进入下阶段准备

后续不要再把精力主要耗在 `LASTEVENT` 这一个缓存点上。  
下个窗口更应该把重心转到：
- `4.8` 标准化测试
- 以及后续视觉链准备

## 补充：给 0 基础看的当前阶段完整理解

这一节不是写给已经熟悉状态机和嵌入式的人看的，而是专门写给“我想真正看懂当前阶段代码到底能干什么”的人。

### 1. 这一阶段系统到底已经能做什么

当前阶段的 `Flytotal / Node A` 已经不是一个“只有零散模块”的工程，而是一条能独立跑通的完整闭环：

1. 雷达可以提供目标位置。
2. `TrackManager` 可以把这些位置整理成“轨迹对象”。
3. `HunterAction` 可以根据轨迹和 RID 状态算出风险分，并决定风险等级。
4. `GimbalController` 可以根据确认后的目标驱动云台进入扫描、获取、跟踪、丢失几种状态。
5. `CloudTask` 可以把当前系统状态整理成统一输出，并在满足条件时创建或关闭事件对象。
6. 用户可以通过串口命令手工注入轨迹、切换 RID、查看状态、查看风险、查看事件。

你可以把这一阶段理解成：

- 雷达负责“发现目标”
- 轨迹模块负责“判断目标是不是连续存在”
- 风险模块负责“判断这个目标危险不危险”
- 云台模块负责“朝目标转过去”
- 事件模块负责“把这次可疑过程变成一个结构化事件”

### 2. 最核心的一条逻辑链怎么走

如果用最通俗的话讲，当前阶段最重要的一条链就是：

`目标出现 -> 形成轨迹 -> 轨迹被确认 -> 风险评分 -> 风险状态升级 -> 事件对象打开 -> 状态输出和上行输出`

再展开一点就是：

1. 雷达给出 `x_mm / y_mm` 位置。
2. `TrackManager` 根据连续出现次数决定：
   - 这个目标是不是 `active`
   - 这个目标是不是 `confirmed`
3. 一旦轨迹被确认，`HunterAction` 开始认真计算风险分。
4. 风险分不是一个黑盒总分，而是多个分项累加：
   - 有目标本身就有基础分
   - 连续出现会增加持续性分
   - 已确认目标会加确认分
   - RID 缺失或可疑会额外加分
   - 距离太近会加分
   - 速度异常也会加分
5. 风险分达到阈值后，不会立刻生硬切换，而是经过“保持窗口”判断是否真的升级。
6. 当风险达到事件级别时，系统创建事件上下文，生成 `event_id`，把事件对象标记为打开。
7. 当风险回落、目标丢失、或者系统复位时，事件会按统一语义关闭，并记录关闭原因。

### 3. 当前阶段最重要的几个模块分别负责什么

#### 3.1 `RadarParser`

它的工作不是判断风险，也不是控制云台。  
它只负责一件事：

- 把雷达发来的原始字节流解析成可用坐标

你可以把它理解成“把雷达语言翻译成人能用的数据”。

#### 3.2 `TrackManager`

它的核心工作是“让目标从一个点，变成一条轨迹”。

它主要解决 3 件事：

- 目标刚出现时，先建立一个 `track_id`
- 连续看到几帧以后，才认为这个目标“确认成立”
- 一段时间没再看到，就认为目标丢失

它的重要意义是：

- 避免看到一个偶然点就立刻当成正式目标
- 给后续风险评分和云台控制一个更稳定的输入

#### 3.3 `HunterAction`

这是当前阶段最关键的“风险判断大脑”。

它负责：

- 计算风险总分
- 保存风险分项
- 根据阈值决定进入哪种风险状态
- 处理升级保持和回落保持
- 输出 `alert / capture / guardian` 这些触发标志

你可以把它理解成：

- `TrackManager` 回答“有没有目标”
- `HunterAction` 回答“这个目标现在有多危险”

#### 3.4 `GimbalController`

它负责：

- 没确认目标时做扫描
- 刚确认目标时先获取
- 确认稳定后持续跟踪
- 目标消失后进入丢失恢复

它不是风险模块。  
它只是根据目标情况决定“云台怎么动”。

#### 3.5 `CloudTask`

它名字虽然像“云”，但你现在可以先把它理解成：

- 当前统一输出中心
- 事件对象管理中心
- 上行状态发布中心

它负责：

- 生成 `UPLINK,HB`
- 生成 `UPLINK,TRACK`
- 生成 `UPLINK,EVENT`
- 管理事件打开、关闭、关闭原因
- 维护 `LASTEVENT` 和 `SUMMARY`

### 4. 当前阶段最关键的参数怎么理解

下面这些参数是这一阶段真正重要的，不只是“写在配置里”的数字。

#### 4.1 云台参数

来源：`include/AppConfig.h`

- `PredictorKp`
  作用：云台预测控制的“跟随力度”。
  变大：云台更积极，反应更快，但过大可能更容易抖。
  变小：云台更稳，但跟踪会更钝。

- `PredictorKd`
  作用：给预测控制增加“刹车感”。
  变大：能压制一部分冲过头，但太大可能显得拖。
  变小：反应直接，但更容易震荡。

- `CenterPanDeg / CenterTiltDeg`
  作用：云台居中角度。
  意义：扫描、复位、默认安全姿态都围绕它。

- `ScanningAmplitudeDeg`
  作用：扫描时左右摆动的幅度。
  变大：扫得更宽。
  变小：扫得更窄，但可能漏掉边缘区域。

- `ScanningPeriodDivisor`
  作用：控制扫描速度。
  数值越大：扫描越慢。
  数值越小：扫描越快。

#### 4.2 轨迹参数

- `ConfirmFrames`
  作用：目标连续出现多少次才算确认。
  变大：更稳，更不容易误判，但响应更慢。
  变小：更快，但更容易把短暂噪声当目标。

- `LostTimeoutMs`
  作用：多久没再看到目标就判定为丢失。
  变大：目标更不容易被判丢失。
  变小：系统更敏感，但可能稍微抖一下就丢。

- `RebuildGapMs`
  作用：如果目标中断太久，再来时就重建新轨迹，而不是沿用旧轨迹。

#### 4.3 风险评分参数

- `TrackingBaseScore`
  含义：只要有活动目标，就先给一个基础风险分。

- `PersistenceScorePerSeen`
  含义：目标每多持续出现一次，风险分增加多少。

- `PersistenceScoreMax`
  含义：持续性分数最多加到哪里为止，防止无限累加。

- `ConfirmedBonusScore`
  含义：目标一旦被确认，就额外再加一笔分，表示“这不是一闪而过的噪声”。

- `RidMatchedScore`
  含义：身份匹配时给负分，相当于降低风险。

- `RidUnknownScore`
  含义：身份未知时加一点风险，但还不算很危险。

- `RidMissingScore`
  含义：身份缺失时明显加分。

- `RidSuspiciousScore`
  含义：身份可疑时加更高的分。

- `ProximityScore`
  含义：目标距离太近时额外加分。

- `MotionAnomalyScore`
  含义：目标速度异常时额外加分。

#### 4.4 风险阈值参数

- `SuspiciousThreshold`
  达到后进入“可疑”。

- `HighRiskThreshold`
  达到后进入“高风险”。

- `EventThreshold`
  达到后进入“事件锁定”，也就是事件对象会被正式打开。

这 3 个阈值的现实意义就是：

- 分数不是只为了显示，而是直接决定系统行为级别。

#### 4.5 保持窗口参数

- `SuspiciousEnterHoldMs`
- `HighRiskEnterHoldMs`
- `EventEnterHoldMs`
- `SuspiciousExitHoldMs`
- `HighRiskExitHoldMs`
- `EventExitHoldMs`

这些参数的意义是：

- 系统不是一过线就立刻升级
- 也不是一掉线就立刻回落
- 要先保持一段时间，确认变化是真的

这套机制的好处是：

- 降低状态来回抖动
- 提高事件语义稳定性

### 5. 你现在最应该记住的状态和命令

#### 5.1 云台状态

- `STATE_SCANNING`
  没确认目标，左右扫描找目标。

- `STATE_ACQUIRING`
  已经看到确认目标，准备进入稳定跟踪。

- `STATE_TRACKING`
  正在持续跟踪目标。

- `STATE_LOST`
  之前有目标，现在暂时丢了，在等待恢复或回到扫描。

#### 5.2 风险相关状态

- `HUNTER_IDLE`
- `HUNTER_TRACKING`
- `HUNTER_RID_MATCHED`
- `HUNTER_SUSPICIOUS`
- `HUNTER_HIGH_RISK`
- `HUNTER_EVENT_LOCKED`

可以把它们理解成：

- 前面几个更像“正在观察”
- 后面几个才是“越来越危险”
- `EVENT_LOCKED` 表示已经进入事件级别

#### 5.3 你最常用的串口命令

最值得记住的还是这几条：

- `HELP`
- `BRIEF`
- `STATUS`
- `RISK,STATUS`
- `EVENT,STATUS`
- `LASTEVENT`
- `TRACK,x,y`
- `TRACK,CLEAR`
- `RID,OK`
- `RID,MISSING`
- `RID,SUSPICIOUS`
- `RESET`

建议你以后看系统时按这个顺序理解：

1. `BRIEF`
   先看“现在大体怎么样”
2. `RISK,STATUS`
   再看“为什么风险会升降”
3. `EVENT,STATUS`
   再看“事件是不是已经打开、为什么关闭”

### 6. 当前阶段最推荐你先看的图

如果你现在想快速真正看懂当前阶段，建议按这个顺序看：

1. `diagrams/flytotal-beginner-logic-map（小白版总逻辑图）.html`
2. `diagrams/flytotal-parameter-glossary（参数词典）.html`
3. `diagrams/main-host-command-map（主机命令影响图）.html`
4. `docs/2026-04-02_node_a_full_logic_map（NodeA全功能逻辑图）.md`
5. 本文件

这样顺序的好处是：

- 先看整体
- 再看参数
- 再看命令
- 再看完整逻辑
- 最后回到阶段结论

### 7. 当前阶段真正还没完成的是什么

当前阶段不是“功能根本没做完”，而是：

- 主链已经能跑
- 风险评分和事件对象已经成型
- 串口查看体验已经明显改善
- 还差的是“更标准化的测试流程”和“视觉链接入准备”

所以后续重点不应该再主要纠缠：

- `LASTEVENT` 某些路径下的缓存小尾巴

而应该更多转向：

- 让测试更标准
- 让操作更清楚
- 让视觉链能顺利接进来

### 8. 最终一次性联调测试（给下一窗口直接执行）

如果要做“功能全部更新后的一次性回归”，固定用下面顺序：

1. 启动网页服务  
`python tools/vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765`

2. 启动串口桥接  
`python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --echo`

3. 跑标准验收套件  
`python tools/track_injector_轨迹注入器.py --port COM4 --suite standard_acceptance`

4. 打开页面  
`http://127.0.0.1:8765`

页面重点验收点：

- 会话摘要里可见套件结论（套件名、PASS/FAIL、通过/失败计数）
- 失败项可从测试结果历史一键跳到时间线并高亮
- 选中检查详情可显示命令/原因/原始串口行
- 复制与导出动作可用（单条、失败清单、完整报告）

建议把 `docs/2026-04-06_node_a_feature_updates（NodeA功能更新）.md` 的 `7.13` 作为最终执行清单主版本。

## 2026-04-09（按 4.10 计划）联合链路验收结论（最新）

### 已完成结果（计划内）

1. 已烧录含 A 方案门槛的固件  
   - 关键参数：`EventConfig::MissingRidEventMinDurationMs = 800`

2. 已执行 4.10 联合套件（风险链 + 事件链 + 视觉触发链）  
   - 命令：  
     `python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --validate-rid MISSING`

3. 验收通过  
   - `suite=risk_event_vision_chain_v1 total=6 passed=6 failed=0`

4. 报文契约核对通过  
   - 命令：  
     `python tools/uplink_packet_contract_check_报文契约核对.py`  
   - 结果：`result=PASS`

5. 交付快照就绪  
   - 文件：`captures/latest_acceptance_snapshot.json`  
   - 关键位：  
     - `suite_ok=true`  
     - `evidence_ready=true`  
     - `contract_ok=true`  
     - `deliverable_ready=true`

### 关键口径确认（计划内）

- 短时无 RID：风险可升，但不直接事件化（场景1 PASS）。  
- 持续无身份 / 身份异常：可升至高风险并进入事件态（场景2/4 PASS）。  
- 高风险阶段：视觉锁定或抓拍预备可触发（场景5 PASS）。  
- 目标丢失：事件可关闭并平稳回落（场景6 PASS）。

### 4.10 结果文件怎么读（下窗口先看这个）

1. `captures/latest_test_session.json`  
   - 作用：执行事实（6 场景是否全 PASS）
2. `captures/latest_joint_chain_evidence.json`  
   - 作用：场景证据（每场景关键行 + 字段）
3. `captures/latest_uplink_contract_report.json`  
   - 作用：接口质量（状态/事件报文契约）
4. `captures/latest_acceptance_snapshot.json`  
   - 作用：交付判定（是否可交付）
5. `captures/latest_delivery_bundle_report.json`  
   - 作用：总闸门汇总  
   - 标注：`非计划必要内容，推荐扩展功能`

### 下一窗口可直接延续（建议执行顺序）

1. 跑 4.10 联合套件  
   `python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --validate-rid MISSING`
2. 跑报文契约核对  
   `python tools/uplink_packet_contract_check_报文契约核对.py`
3. 快速确认交付快照  
   `python -c "import json;print(json.dumps(json.load(open('captures/latest_acceptance_snapshot.json','r',encoding='utf-8')),ensure_ascii=False,indent=2))"`

### 下一窗口可直接延续（承接结论）

从当前状态进入下一窗口时，默认以 `risk_event_vision_chain_v1` 作为 4.10 基线回归套件；若后续扩展新功能，先保证该套件不回退。

---

## 2026-04-12（4.12 固化日）联调补充更新（给下周直接接续）

### A. 当天最终状态（冻结结论）
1. 已完成 `Node A Hunter+Vision+Web Demo V1.0` 冻结口径。
2. 已拿到真机闭环证据：真实目标 -> 事件创建 -> 视觉锁定/抓拍 -> 网页详情展示 -> 证据导出。
3. 自动验收口径已跑通：`quick_result=PASS`、`full_result=PASS`、`result=PASS`。
4. 样例事件已成功挂图：`A1-0000002622-0001`（`event_id` 精确匹配）。

### B. 4.12 硬件联调高频问题与根因（重点）

#### B1. COM4 端口冲突（最常见）
现象：
1. `Failed to open COM4: PermissionError(13, '拒绝访问。')`

根因：
1. 串口独占；同一时刻只能一个进程占 `COM4`。
2. 常见占用者：旧 `node_a_serial_bridge`、`miniterm`、串口监视器、烧录进程。

解决：
1. 查占用进程并结束后再启动目标程序。
2. 固定规则：烧录前停桥接；串口诊断前停桥接；测试完再恢复桥接。

#### B2. 看起来“有坐标但一直 track_active=0”
现象：
1. `x_mm/y_mm` 有值，但 `track_active=0`、`track_confirmed=0`、`gimbal=SCANNING`。

根因：
1. 可能读到旧快照（桥接未运行或文件未刷新）。
2. 也可能是最后一次坐标残留值，不代表当前活跃轨迹。

解决：
1. 先确认桥接进程在跑。
2. 再看 `captures/latest_node_status.json` 的更新时间是否持续刷新。
3. 只用实时刷新数据判断状态，不用单次静态值判断。

#### B3. 读错状态文件导致误判
现象：
1. 查询舵机字段返回 `None` 或字段异常。

根因：
1. 读了视觉文件 `captures/latest_status.json`，不是主链文件。

解决：
1. 主链状态统一看：`captures/latest_node_status.json`。
2. 视觉状态看：`captures/latest_status.json`。

#### B4. 网页/接口像“旧版本”
现象：
1. 新接口 404 或网页看起来没更新。

根因：
1. 旧 `vision_web_server` 进程还占着 `8765`，新代码没被加载。

解决：
1. 清理旧进程，确认 `8765` 无占用后重启网页服务。
2. 浏览器强刷（Ctrl+F5）避免前端缓存误导。

#### B5. vision_bridge 偶发 Permission denied 并退出
现象：
1. `PermissionError: ... latest_node_status.json`

根因：
1. Windows 下桥接原子写替换文件瞬间，视觉进程读文件撞锁。

解决（已修复）：
1. 在 `tools/session_log_utils_会话日志工具.py` 的 `load_json_payload()` 增加了短重试容错。
2. 该修复是稳定性修补，不改业务逻辑。

#### B6. 舵机不跟目标、仍左右扫描
现象：
1. 雷达似乎看到目标，但云台仍 `SCANNING`。

根因：
1. 状态机按 `track_confirmed=1` 进入跟踪；仅有瞬时坐标不够。
2. 若 `test_mode_enabled=1`，自动控制会被测试模式覆盖。

解决：
1. 先看组合：`track_active/track_confirmed/gimbal_state/test_mode_enabled`。
2. 退出测试控制：`DIAG,STOP`、`TESTMODE,OFF`、`SAFE,OFF`。
3. 仅当 `track_confirmed=1` 才要求云台稳定跟踪。

### C. 摄像头与云台关系（工程口径）
1. 电气上可分开：USB 摄像头接电脑，舵机+雷达接 Node A。
2. 工程上建议机械同向或同轴：否则雷达/云台角度可能超出摄像头视场，抓拍会空拍。
3. 当前版本定位：`手动起锁（s 选框） + 自动/手动抓拍`，不是自动检测起锁版本。

### D. 固定启动/验收顺序（下周继续直接用）
1. 启动桥接：`python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200`
2. 启动视觉：`python tools/vision_bridge_视觉桥接.py --backend dshow --source 1 --tracker csrt --tracker-fallback auto --source-warmup-frames 20`
3. 启动网页：`python tools/vision_web_server_视觉网页服务.py`
4. 自动验收：`python tools/acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --base-url http://127.0.0.1:8765`

### E. 下周接续建议（不重复踩坑）
1. 每天开发前先跑一次自动验收守门（PASS 再推进新任务）。
2. 所有硬件问题先排“资源占用/是否实时/是否读对文件”，再排算法。
3. 自动找目标属于下周新方向，建议在现有 `vision_bridge` 上增量实现“检测器自动起锁”，保留手动模式作为兜底。

---

## 2026-07-08 云端 LLM 闭环联调补充

### A. 当前状态

NodeA 云端大模型链路已实测跑通：

```text
CLOUD,QUEUED,source=TEST
CLOUD,CMD,TRIGGER_PARACHUTE,effect=PARACHUTE_INTENT_LOGGED,status=NOT_INTEGRATED
CLOUD,STATUS,enabled=1,configured=1,wifi=CONNECTED,cloud_online=1,threat_level=HIGH,command_type=TRIGGER_PARACHUTE,cloud_command_effect=PARACHUTE_INTENT_LOGGED,cloud_command_source_event_id=A1-CLOUD-TEST,error=NONE
```

这说明“边缘事件上传 -> Ark 大模型研判 -> 云端指令下发 -> NodeA 安全审计记录”已经闭环。

本窗口又进一步跑通了真实风险事件触发云端闭环，不再只停留在 `CLOUD,TEST`。核心证据如下：

```text
RISK,STATUS,...main_state=EVENT,current_risk_state=EVENT_LOCKED,risk_score=84.0,risk_level=EVENT,...event_active=1,event_id=A1-0000456030-0001
CLOUD,CMD,GENERATE_ALERT,effect=ALERT_GENERATED
CLOUD,STATUS,enabled=1,configured=1,wifi=CONNECTED,cloud_online=1,threat_level=HIGH,command_type=GENERATE_ALERT,cloud_command_effect=ALERT_GENERATED,cloud_command_source_event_id=A1-0000456030-0001,error=NONE
SUMMARY,...risk_event=1,event_opened=1,event_closed=1,max_risk=84.0,last_event_id=A1-0000456030-0001
```

这说明真实风险链已经完成：

1. `RID,MISSING + 近距离持续 TRACK` 把风险推到 `84.0`，进入 `EVENT_LOCKED`。
2. 事件对象真实打开，事件号为 `A1-0000456030-0001`。
3. 云端 LLM 返回 `GENERATE_ALERT`，NodeA 侧记录 `ALERT_GENERATED`。
4. `cloud_command_source_event_id` 绑定真实事件号，不是测试事件号。

网页证据链也已经补齐云端字段：

1. `event_object_v1` 会带上 `cloud_online / cloud_threat_level / cloud_command_type / cloud_command_effect / cloud_command_source_event_id` 等字段。
2. 只有当 `cloud_command_source_event_id` 与当前事件号一致时，网页服务才把当前云端状态合并进事件对象，避免误绑定。
3. Dashboard 事件详情新增云端在线、云端威胁、云端命令、边缘执行、云端来源事件、云端建议。
4. 事件证据导出 JSON 会携带同一组云端字段。

国一材料优先引用两条证据，不要混成一条讲：

1. `A1-0000307059-0003` 负责证明云端告警执行。导出包为 `captures/event_exports/event_evidence_A1-0000307059-0003_1783518461715.json`，证据哈希 `105044217ebc9673f664d513d2ab3804d400292b0a3b7f7c4be86420269b6ef1`。关键字段：`risk_score=84.0`、`cloud_online=1`、`cloud_command_type=GENERATE_ALERT`、`cloud_command_effect=ALERT_GENERATED`、`cloud_command_source_event_id=A1-0000307059-0003`。边界：`capture_count=0`，所以它主要证明云端研判和边端执行闭环。
2. `A1-0000003139-0001` 负责证明图像抓拍绑定和网页导出证据链。导出包为 `captures/event_exports/event_evidence_A1-0000003139-0001_1783521642679.json`，证据哈希 `227e1b5a9fbe4907f45c4fb4cec0ca47eac82d5708ae627afe196cf824ce8da6`。关键字段：`capture_count=1`、`capture_binding_mode=event_id_exact`、`cloud_online=1`、`cloud_command_type=ADJUST_THRESHOLD`、`cloud_command_effect=EVENT_THRESHOLD_70`、`cloud_command_source_event_id=A1-0000003139-0001`。抓拍文件为 `captures/2026-07-08_22-40-31_616ms_f631616_cap001_cloud_threshold_bind_A1-0000003139-0001.jpg`。

### B. 本轮关键修复

1. 原故障为 `http_request_failed`，底层 `esp_error=28674`。
2. `28674 = 0x7002 = ESP_ERR_HTTP_CONNECT`，属于 HTTPS 连接打开失败。
3. 根因是 Arduino + PlatformIO 下 `esp_crt_bundle_attach` 没有对应的证书 bundle 数据初始化。
4. 已在 `lib/CloudClient/CloudClient.cpp` 中切换为显式 `DigiCert Global Root G2` 根证书 PEM：

```cpp
config.cert_pem = kArkRootCaPem;
config.cert_len = sizeof(kArkRootCaPem);
```

### C. 已完成验收

```powershell
pio run
pio run -t upload --upload-port COM4
python tools\firmware_safety_checks.py
```

结果：

```text
pio run: SUCCESS
upload COM4: SUCCESS
firmware_safety_checks: PASS
```

### D. 下个窗口优先事项

1. 先不要重复排查 API Key、模型名、热点 2.4 GHz，这些已经确认可用。
2. 真实事件触发云端闭环已经跑通，下一步优先做视频证据和网页侧展示证据。
3. 视频建议覆盖：真实目标/模拟轨迹进入、`RISK,STATUS` 到 `EVENT`、云端返回 `GENERATE_ALERT`、`CLOUD,STATUS` 显示 `cloud_online=1` 和 `error=NONE`。
4. `TRIGGER_PARACHUTE` 当前只代表处置意图记录，硬件未集成时必须继续保留 `NOT_INTEGRATED` 口径。
5. 下一步不要改动主链大结构，优先启动网页和串口桥接，用真实事件跑一遍并导出 JSON 证据包。

---

## 2026-07-09 视觉演示稳定性修复补充

### A. 当前状态

昨天采集 `A1-0000003139-0001` 图像绑定证据时，发现当前 Python/OpenCV 环境没有 `CSRT/KCF` tracker，但有 `TrackerMIL_create`。旧版视觉桥接只允许 `csrt/kcf`，会显示 `Available trackers: NONE`，导致录屏前需要临时运行时补丁。

今天已把 `MIL` tracker 正式接入：

1. `tools/vision_bridge_视觉桥接.py` 支持 `csrt/kcf/mil`。
2. `tools/usb_camera_readiness_check_USB摄像头就绪核对.py` 支持检测和推荐 `MIL`。
3. 默认优先级仍为 `csrt -> kcf -> mil`，有更强 tracker 的环境继续优先使用原方案；当前机器自动 fallback 到 `MIL`。

### B. 已验证命令

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

### C. 下个窗口优先事项

1. 录屏前先运行摄像头预检，确认推荐命令仍为 `--tracker mil` 或更高优先级 tracker。
2. 推荐视觉桥接启动命令：

```powershell
python tools\vision_bridge_视觉桥接.py --backend dshow --source 0 --tracker mil --tracker-fallback auto --source-warmup-frames 12
```

3. 录屏目标不要只录串口，要同时录网页事件详情和导出 JSON。
4. 保持两条证据分工：`A1-0000307059-0003` 讲云端告警执行，`A1-0000003139-0001` 讲图像绑定完整导出。

---

## 2026-07-12 国一冲刺 Day 1：自动视觉与网页证据升级

### A. 已完成

1. 修复单类别无人机 YOLO 输出 `[1, 5, 8400]` 的解码方向，模型结果可正常进入运行链。
2. 增加 `YOLO_AUTO`：模型连续两次确认同一目标后，自动初始化可用的 MIL tracker，不再依赖人工按 `s` 选框。
3. 增加黑帧、白帧和平坦帧守门；无效画面不保存 JPG，也不写入抓拍记录。
4. NodeA 状态过期或离线时，不再把新抓拍绑定到历史事件号。
5. 网页事件详情和导出对象已接入锁定来源、模型分数、画面质量、抓拍 SHA256 与独立视觉证据 SHA256。
6. 修复真实/模拟模式切换竞态、mock 哈希漂移和手机整页横向溢出。

### B. 已通过验收

1. 视觉离线回归：`PASS (6/6)`。
2. 摄像头预检：摄像头 0 可读，`frame_quality_reason=OK`，本机可用 tracker 为 `MIL`，无人机模型可加载。
3. 保留样本自动闭环：`READY_ONNX -> YOLO_AUTO -> VISION_LOCKED -> MIL TRACKING -> AUTO_LOCK capture`。
4. PlatformIO 编译成功，RAM `15.7%`，Flash `30.1%`；固件安全检查 `PASS`。
5. 桌面和手机真浏览器验收均为：0 页面错误、0 控制台错误、0 失败请求、无整页横向溢出、叠加画布非空。
6. 同一 mock 事件经过 2 秒自动刷新后，抓拍哈希和 64 位视觉证据哈希保持一致。

### C. 重要边界

1. 自动闭环当前使用保留测试集图片生成的临时视频，不是外场真无人机证据。
2. mock 页面只用于验证界面、字段和哈希逻辑，不能写成真实实验。
3. 7 月 8 日事件 `A1-0000003139-0001` 的抓拍平均亮度约 `0.02`，属于黑帧，不再作为国赛主视觉证据。
4. 2026-07-12 最新串口枚举仍为 `NONE`，所以尚未生成“新 NodeA 事件 + 自动视觉 + 云端同事件指令 + 网页导出”的同场证据。

### D. 当前服务与文件

- 看板地址：`http://127.0.0.1:8765/vision_dashboard.html`
- 当日记录：`docs/2026-07-12_node_a_feature_updates（NodeA功能更新）.md`
- 桌面截图：`outputs/e2e/2026-07-12_dashboard_vision_evidence_desktop.png`
- 手机截图：`outputs/e2e/2026-07-12_dashboard_vision_evidence_mobile.png`

### E. 下一步唯一优先事项

接回 NodeA 串口后，立即采集一条全新的同场闭环证据。录屏必须同时出现：新事件号、`YOLO_AUTO`、无人机类别/分数、有效画面、云端同事件指令、网页事件详情、导出 JSON 与哈希。完成前不得把 Day 1 标成“已具备国一实证”。

---

## 2026-07-12 同一事件严格证据闭环补充

### A. 比赛口径

1. 当前目标是 **2026 全国大学生物联网设计竞赛乐鑫命题**，不是嵌入式芯片与系统设计竞赛。
2. 官方硬要求为乐鑫指定 ESP32 核心控制器、至少一种传感器融合、至少一个云端大模型，以及设备与大模型之间的上行或下行闭环。
3. 官方作品提交截止时间为 `2026-07-27 24:00`。

### B. 本轮完成

1. `node_a_serial_bridge` 新增视觉状态转发。NodeA 串口桥独占 COM 口并读取 `captures/latest_status.json`，把新鲜视觉状态转换为固件已支持的 `VISION,...` 指令。
2. 锁定只有在视觉源、模型链、锁定标志和画面质量全部有效时才下发；过期或无效状态会清锁。
3. 网页合并增加视觉状态新鲜度判断，旧主机状态不再覆盖设备状态。
4. 单节点闭环新增 15 项严格证据门槛，完整检查自动识别、有效截图、同一事件云端下行与双层哈希。
5. `acceptance_flow --mode full` 默认打开严格门槛；`quick` 仍只负责快速排查环境。
6. 启动助手生成的 NodeA 命令已默认带 `--vision-forward-status`。
7. 严格导出使用导出瞬间的内嵌快照做第二次 15 项核验，再用该快照哈希核对落盘文件，消除实时跟踪更新导致的哈希竞态。
8. `track_injector` 改为串口打开成功后才重置运行态文件；无效 COM 不再清空已有事件和会话证据。

### C. 验证证据

```text
python py_compile: PASS
vision_regression_checks: PASS (10/10)
baseline closure: PASS
full mode default: closure_require_national_first_evidence=true
historical event strict gate: FAIL (8/15)
web stale merge: vision_runtime_online=0, detector_state=OFFLINE
strict export fixture: PASS (15/15 + saved hash replay)
invalid COM preservation: PASS (session/event SHA256 unchanged)
```

历史事件 `A1-0000003139-0001` 严格失败是正确结果。它没有有效 YOLO 自动视觉证据，导出中的视觉哈希也不能与当前严格详情相互证明，因此不得继续当作国一主证据。

### D. 当前阻塞与下一动作

1. 当前系统未发现串口，真实视觉回传 ESP32 尚未实机验证。
2. 板子重新出现后，第一终端使用：

```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200 --vision-forward-status
```

3. 同一现场完成一条新事件：真实传感器触发 -> YOLO 自动锁定 -> 有效截图 -> 云端 LLM 同事件下行 -> NodeA 执行记录 -> 网页严格导出。
4. 只有严格验收达到 `15/15 PASS`，才把该事件收入国赛主证据。

### E. 三终端资源所有权（必须按此执行）

1. 真实现场运行时，`node_a_serial_bridge` 是唯一串口所有者，`vision_bridge` 是唯一摄像头所有者。
2. 三终端都在运行时，验收命令必须带：`--no-run-suite --skip-usb`。
3. 当前启动助手已自动生成无冲突命令：

```powershell
python tools/acceptance_auto_411_快检全检自动验收.py --port COM4 --suite risk_event_vision_chain_v1 --no-run-suite --skip-usb --base-url http://127.0.0.1:8765
```

4. 只有做台架模拟轨迹套件时才停止常驻串口桥，并改用 `--run-suite --skip-usb`。
5. 已验证 live full 只执行 `single_node_evidence_closure`，不会启动 `track_injector`；auto quick/full 也正确透传 `--no-run-suite`。
6. 无效 COM 测试中，事件快照与会话文件 SHA256 均保持不变。

---

## 2026-07-13 V4b 候选模型与运行链验收

### 已完成

1. 修正源数据类别映射，两个真实无人机类别都统一为项目类别 `0:drone`。
2. 完成 V4b 困难负样本训练与独立 5000 张 COCO val2017 评测，`best.pt` 为当前候选。
3. 候选 ONNX 已导出为 `models/yolov8n_drone_v4b_candidate.onnx`，SHA256 为 `c33aba9e6e24ce24ae6147a538b46b0c1080093242f0ad1c59100c738121ac74`。
4. 修复 Sidecar 非方形画面直接拉伸问题，改用 `640x640` letterbox，并正确还原检测框。
5. 同一 103 张图上，Sidecar 已与 PyTorch 和 Ultralytics ONNX 完全一致：`TP=85, FP=4, FN=24, R=77.982%`。
6. 475 张 CPU 验收：平均 `30.555 ms`、P95 `34.816 ms`；333 张重点 COCO 误触 `17`，39 张本地背景误触 `0`。
7. Python 语法检查与视觉回归 `11/11` 通过。
8. 默认 ONNX/OpenCV 线程池长跑争用已定位；正式 Sidecar 固定 8 个 ONNX 单次推理线程，保留两次失败长跑和最终通过数据，不隐藏异常。

### 当前边界

1. V4b 已获授权并部署到 `models/yolov8n_drone.onnx`；原 V1 已按原哈希备份，可随时回滚。
2. COM4 当前未枚举，真实同一事件严格 `15/15` 尚未补采。
3. 外场真无人机、人、车、鸟、距离与现场视频仍未完成，不能把离线指标写成外场能力。

### 下一动作

先完成 V4b 部署后的正式模型哈希、结构、精度、延迟与完整回归。通过后立即回到 2026-07-12 第 2 步补同场 `15/15`，随后执行 2026-07-13 第 4 步外场实测。

---

## 2026-07-13 COM4 单一入口稳定性补充

### 已完成

1. 常驻 `node_a_serial_bridge` 已改为唯一发送调度器，内部所有轮询、重复命令、视觉转发和临时命令按优先级顺序发送，不再同一轮集中直写串口。
2. 新增 `tools/node_a_serial_command_NodeA串口命令.py`，通过本地原子请求文件提交命令，不打开 COM4。
3. 状态命令只保留最新值，动作命令逐条保留；安全清除可抢占低优先级查询，并且不会被旧轨迹覆盖。
4. 默认全局发送间隔为 `0.10 s`、队列上限为 `64`、外部请求有效期为 `30 s`。

### 验收

```text
python py_compile: PASS
vision_regression_checks: PASS (12/12)
live COM4: one bridge process / one serial connection
11 external requests accepted / 0 pending / 0 stderr bytes
NodeA uptime remained monotonic; no reconnect reset
```

当前低风险发命令方式：

```powershell
python tools\node_a_serial_command_NodeA串口命令.py "CLOUD,STATUS"
```

不要再为了发送一条临时命令停止桥接或另开串口监视器。

### 仍未完成

1. `track_injector`、单板测试和 RID 模拟器仍直接拥有串口，只能在常驻桥接停止后运行；尚未迁移到统一入口。
2. `vision_bridge` 的 `latest_status.json` 原子替换仍缺少 Windows 文件占用重试，曾因此退出一次。
3. 同一真实事件的云端、视觉、抓拍和严格 `15/15` 证据仍需重新采集。

---

## 2026-07-13 视觉状态写入并发稳定性补充

### 已完成

1. `vision_bridge` 原子替换 `latest_status.json` 遇到 Windows `PermissionError` 时，按 `10` 次、`0.05 s` 间隔有限重试；状态内容只写一次，不会在重试中改变载荷。
2. 新增回归用例模拟首次替换被占用、第二次成功，完整视觉回归提升为 `13/13 PASS`。
3. 20 秒高争用实测后，视觉进程和 COM4 串口桥接均存活；视觉状态保持 `VISION_LOCKED / READY_ONNX / YOLO_AUTO`，状态年龄约 `133 ms`，两者 stderr 均为 `0`。

### 当前边界与下一动作

1. 写入端退出问题已修复，但网页服务的直接读取路径尚未处理 `PermissionError`。同一轮压力测试出现网页请求断开与请求线程异常，因此整条文件并发链路还没有完成。
2. 下一项仍属于 2026-07-12 第 2 步：只给 `vision_web_server` 的状态文件读取增加有限重试并重复同一压力测试。完成后再继续同一真实事件云端、视觉、抓拍和严格 `15/15` 闭环。
3. 当前稳定性测试使用保留数据集视频，不是外场真无人机证据。

---

## 2026-07-13 网页状态读取并发稳定性补充

### 已修改

1. `vision_web_server.load_json_file` 读取状态文件遇到 `PermissionError/OSError` 时按 `6` 次、`0.03 s` 间隔有限重试。
2. 若短暂占用解除，正常返回原 JSON；若连续达到上限，返回 `ok=false, available=false, error=read_denied`，不再抛出请求线程 traceback。
3. 新增恢复路径和重试耗尽路径回归，完整视觉回归为 `14/14 PASS`。
4. 在视觉写入进程持续刷新状态时完成 20 秒高争用复验：直接文件读取 `477` 次成功、`10` 次瞬时冲突，HTTP `487/487` 成功且断开为 `0`。
5. 视觉 PID `42740`、网页 PID `26940`、COM4 桥接 PID `7744` 均存活；状态年龄 `84 ms`，三份 stderr 均为 `0`。写入与网页读取并发链路已完成。

### 后续顺序

立即回到 2026-07-12 第 2 步同一真实事件云端、视觉、抓拍和严格 `15/15` 闭环；外场真无人机证据仍属于 2026-07-13 第 4 步。当前临时使用公用网络，云端实测留到用户切回 W-iPhone 热点后执行；本地离线准备与验证可继续。

---

## 2026-07-13 同一事件定时命令准备

### 已完成

1. 统一命令工具新增 `--interval-s`，可以在不打开 COM4 的前提下按时间顺序提交重复状态命令。
2. 默认间隔为 `0`，不改变原有行为；同一事件重复 `TRACK` 确认建议使用 `0.20 s`，高于调度器 `0.10 s` 最小发送间隔。
3. 完整视觉与串口回归为 `15/15 PASS`；临时收件箱离线测试生成 `3/3` 个独立请求、顺序正确、无临时文件残留。
4. 用户不在设备旁期间未向 COM4 发送运动命令，未驱动云台。

### 回来后的用途

切回 W-iPhone 并确认设备旁有人看守后，使用定时统一入口生成新事件，保持常驻串口桥不退出；随后完成 YOLO 自动锁定、同事件抓拍、云端下行和严格导出。

---

## 2026-07-13 视觉心跳串口节流

### 已完成

1. 定位到“COM4 枚举且板端仍回复视觉命令，但 NodeA 状态长期离线”的根因是视觉双命令心跳占满调度容量，不是串口断线。
2. 首次锁定或置信度变化仍发送 `VISION,CONF + VISION,LOCKED`；未变化的重复心跳只发送 `VISION,LOCKED`。
3. 使用原压力参数 `vision-forward-interval=0.25 s`、`serial-min-send-interval=0.10 s` 重启桥接，20 秒持续检查中 `STATUS`、`EVENT,STATUS`、`LASTEVENT` 均持续回包。
4. NodeA 保持 `online=1`，状态年龄 `146 ms`，桥接 stderr 为 `0`，PID `29824` 存活。

### 结论

以后看到进程存活但状态变旧时，先检查调度负载和板端是否仍回复，不要直接要求拔插开发板。当前视觉转发与状态轮询已经能在同一 COM4 所有者内稳定共存。

---

## 2026-07-13 真实轨迹采集门禁与距离证据边界

### 已完成

1. 真实轨迹采集器默认状态源从旧的 `captures/e2e_node_status.json` 修正为当前 `captures/latest_node_status.json`。
2. 新鲜度门禁联合使用 `stale_age_ms + 文件经过时间`、主机 `last_update_ms`、文件更新时间和 `online`，桥接退出后的冻结状态不能继续写入 CSV。
3. 开启 `--active-only` 后，只有 `track_active=1` 与 `track_confirmed=1` 同时成立才写行；CSV 列结构及分类器接口未改变。
4. 原真实数据 SOP 已原位更新：LD2450 只提供经实测确认的近距二维轨迹；V4b 负责视觉距离表现；LD2451 负责远距运动预警。10/30/50 米不能直接冒充 LD2450 轨迹能力。
5. Python 编译和完整回归通过，回归总数由 `15/15` 增至 `16/16`。当前实时状态命令行采集 `4/4` 行通过；旧 e2e 状态 `4/4` 被拒绝，未写入正式数据集。

### 下一步

用户回到设备旁后，先切回 W-iPhone 并打开最大兼容性，再执行真实无人机、人物、车辆、鸟类和实测距离分层；近距轨迹、视觉距离、远距预警分别保留原始证据。随后完成云端/API 和同一真实事件严格 `15/15`，不得用本地软件回归 `16/16` 代替。

---

## 2026-07-13 真实轨迹重复会话保护

### 已完成

1. 采集器会在写入前检查正式 7 列 CSV 结构，以及同标签、同 `session-id` 的既有 `track_id`。
2. 重复会话默认以 `SESSION_ID_EXISTS` 中止，避免两段从 `0 ms` 开始的时间轴被分类器合并；相似前缀和其他标签不误拦截。
3. `--allow-session-reuse` 仅保留给调试，正式现场数据必须每段使用新编号。
4. 旧现场 runbook 已缩减为当前 `2026-06-08_real_data_collection_sop_v1.md` 的入口，不再保留旧状态路径和未经实测的 LD2450 距离表。
5. 编译和回归为 `16/16 PASS`；真实当前状态首次临时采集 4 行，第二次相同会话在写入前拒绝，文件仍为 4 行。

### 现场规则

会话编号最后一段必须递增，例如 `_01`、`_02`。若上一段已经写入部分有效行，也不要覆盖或复用编号；保留它作为失败/中断记录，再使用新编号重采。

---

## 2026-07-13 干净真实数据基线与分类来源隔离

### 已完成

1. 审计发现旧 `real_tracks.csv` 只有 50 行全零 `clutter`、1 条轨迹，无当前门禁和现场元数据，分类验收召回为 0。
2. 旧 CSV 以原 SHA256 `c574ae68e53833e9ebdeb6c0a7a126970387e26eedece2a81391ee363a4686b3` 无损保存到 `datasets/drone_recognition/raw/archive/`，归档仍为 50 行并附审计 JSON。
3. 活动 `real_tracks.csv` 只保留 7 列表头、0 行，现场采集从干净基线开始。
4. 修复分类器空真实输入自动退回 mock 的问题：`--input` 与 `--mock` 现在显式二选一；空真实输入返回 `no_real_tracks`、`ok=false`、非零退出，并清除同输出目录的旧图表，不产生合成结果或模型。
5. 显式 mock 仍为 12 条；有效 `sample_tracks.csv` 验收保持 accuracy/recall 均为 1.0；完整回归增至 `17/17 PASS`。
6. 数据目录 README 已同步当前唯一 SOP、干净 0 行活动基线、唯一 `session-id` 和禁止正式数据使用两个调试覆盖开关的规则。

### 当前真实状态

真实轨迹数据量现在诚实地为 0。只有用户回到合法安全场地，完成无人机、人物、车辆、鸟类和距离分层采集后，才允许生成和引用真实分类指标。

---

## 2026-07-13 物联网竞赛一页摘要与场景矩阵收口

### 已完成

1. 以乐鑫 2026 官方命题页重新确认四条硬要求，并在一页摘要中逐项映射 ESP32-S3、多源融合、火山方舟豆包和结构化上行/受控下行。
2. 一页摘要已删除未经当前现场证明的 `5-100 m 检测`、估算 `16 ms 实测` 和旧 CSRT 描述，改为有证据数值与 `PENDING` 分栏。
3. 当前架构明确为 PC 网关执行 V4b ONNX，ESP32-S3 执行传感融合、事件决策、云端通信和指令策略，避免答辩时把主机推理冒充 MCU 推理。
4. V4b 模型卡已修正部署状态；正式模型仍是 V4b，V1 仅为可回滚备份。
5. 现有场景矩阵新增真实目标与距离表，台架 PASS 与外场 PENDING 分开；没有给任何未测试格填写成功。

### 回来后填写规则

只根据原始视频、实测距离、状态 JSON、事件导出和哈希填写矩阵。失败填 `FAIL`，受场地或镜头限制填 `NOT_TESTABLE` 和原因，不通过调低阈值或引用离线数据改成 PASS。

---

## 2026-07-13 答辩日运行入口 V2

### 已完成

1. 5 月 demo runbook 已更新为当前 W-iPhone、COM4 单一入口、摄像头 readiness、V4b、Dashboard 和严格验收流程。
2. 真实模式不允许模拟 `TRACK`；台架 fallback 必须标注模拟并由统一收件箱提交，避免第二个串口拥有者。
3. 常驻服务下固定使用 `acceptance_auto --no-run-suite --skip-usb`，随后运行 `--require-national-first-evidence` 核对同事件 `15/15`。
4. 90 秒脚本按“硬件 -> 多源状态 -> 豆包 -> 边缘响应 -> 抓拍/哈希 -> 15/15”展开，直接对应物联网赛要求。
5. 失败回退只允许分别展示视觉、云端和严格失败包，不把不同日期证据剪成一条成功事件。

### 用户回来后的第一件事

切回 W-iPhone 并打开最大兼容性。确认人在设备旁、安全条件允许后，再按 runbook 从网络、摄像头和云端预检开始；当前公共网络下不要执行云端闭环或无人看守的轨迹/舵机命令。

当前源码已按 runbook 实际复核：PlatformIO 构建 `SUCCESS`，RAM `15.7%`、Flash `30.1%`；PC 完整回归 `17/17 PASS`。本轮没有刷写开发板。

---

## 2026-07-13 误报漏报证据口径 V2

### 已完成

1. 误报漏报表不再用台架回归支持“未发现误报漏报”，改为台架、离线视觉、外场真实三层。
2. V4b 独立集明确为 Precision `0.95506`、Recall `0.77982`、`FN=24`；COCO 5000 张压力触发为 `120/5000`。
3. 分类触发中飞机为 `15/97`，人物 `58/2693`、车辆 `18/535`、鸟 `4/125`、风筝 `4/91`，只称图片触发率，不称现场误报率。
4. 10/30/50 米真实矩阵和 20 分钟长稳全部保持 `PENDING`，等待原视频和距离记录。

### 决策

先执行原计划真实实测，不立即开始 V5 再训练。若外场确认飞机/鸟/车辆连续误锁，再把针对性难负样本训练标为“非计划必要内容，推荐扩展方向”，单独申请后执行。

---

## 2026-07-13 答辩 Q&A 证据收口

### 已完成

1. Q&A 已改为乐鑫物联网主线，补齐 ESP32-S3 核心、结构化传感上行、豆包 JSON 下行、边缘安全执行和断网降级。
2. 删除没有原始记录支持的天气置信度、帧数误报率和固定距离不受影响承诺。
3. 当前雷达轨迹确认参数已按代码修正为 `ConfirmFrames=3`；V4b 自动起锁是独立的两次稳定检测。
4. PC 视觉、模拟 RID、单节点 handoff 预留和未集成降落伞均明确边界。
5. Q&A 直接承认当前还不能保证国一，缺口是同事件 `15/15`、真实外场统计、稳定演示和物理完成度。

### 使用方式

答辩时优先讲“做了什么、证据在哪里、没测什么”，不要背旧版漂亮数字。评委继续追问时打开一页摘要、模型卡、场景矩阵或事件导出对应字段。

### 云端预检补充

AI 云端默认关闭。用户回来后必须按顺序经收件箱执行 `CLOUD,ENABLE,1`、独立 `CLOUD,TEST`、等待结果、`CLOUD,STATUS`；只有 `enabled/configured/wifi/cloud_online/error` 全部符合预期才开始主事件。测试事件不能当最终同场证据，之后必须产生新事件号。公共网络期间未执行上述命令。

---

## 2026-07-13 启动助手正式 V4b 命令冻结

### 已完成

1. readiness 推荐和无报告 fallback 均显式固定 `yolov8n_drone.onnx`、V4b 部署标签、`0.45`、8 线程和自动锁定。
2. 启动助手不再原样信任旧 readiness 的命令字符串，而是使用其 source/backend/tracker 字段重建当前模板。
3. 旧 readiness 报告实测重建为 `py -3 + dshow + source 0 + MIL + V4b`，用户选择的 Python 命令未丢失。
4. Python 编译和完整回归通过，回归总数增至 `18/18`；测试未打开 COM4。

用户回来后仍应先刷新一次真实摄像头 readiness；结构化重建只保证命令不会降级，不替代当天摄像头画面检查。

---

## 2026-07-13 离线总验收与严格门槛反向验证

### 已完成

1. Python 工具编译、视觉完整回归 `18/18`、固件安全检查和 PlatformIO 构建均通过；RAM `15.7%`、Flash `30.1%`。
2. 本地网页为 live 模式，A1 在线且由 PID `29824` 的唯一桥接进程占用 COM4；本轮没有发送串口命令或刷写固件。
3. runbook 正式 V4b 示例命令补齐 warmup `12` 和显式自动锁定，与 readiness/启动助手保持一致。
4. 在没有新主事件的当前状态运行严格门槛，正确得到 `FAIL (3/15)`、退出码 `2`；16 项缺失证据被明确列出，自动导出未发生。

### 结论

本地软件入口已收口，严格门槛没有假阳性。视觉 `OFFLINE` 是有限录像播放完毕后的正常状态。用户回来后按顺序切回 W-iPhone 最大兼容性、刷新真实摄像头 readiness、完成云端预检、生成全新主事件，再运行严格 `15/15`；旧事件和云端测试事件都不能替代新主事件。

---

## 2026-07-13 严格 15/15 正向可达性回归

### 已完成

1. 回归新增正式 CLI + localhost API 级正向夹具，不再只验证内部判定函数和直接导出构造器。
2. 临时同事件证据通过主门槛 `15/15`，严格导出快照再次通过 `15/15`，导出回放、事件哈希和视觉哈希均通过。
3. 完整回归增至 `19/19 PASS`；测试使用随机本地端口和系统临时目录，没有打开 COM4、摄像头或公网。
4. 当前正式证据再次核对仍为预期 `FAIL (3/15)`、退出码 `2`，临时夹具未污染真实证据。

### 边界

这个测试证明验收器“完整时能过、缺失时会拒绝”，不证明豆包当前在线，也不证明真实无人机识别。用户回来后仍必须以全新真实事件完成正式 `15/15` 和外场矩阵。

---

## 2026-07-13 新主事件时间防伪门槛

### 已完成

1. `--require-national-first-evidence` 默认增加最近 15 分钟的主机记录时间限制，使用事件 `host_logged_ms`，缺失、过期或明显未来时间均失败。
2. 新鲜度是 15 项内容之外的前置条件；过期事件即使内容 `15/15` 也不会自动生成严格导出。
3. CLI 级 stale 回归用 16 分钟前的完整事件验证：内容 `15/15`，总体因 `event_stale` 失败，自动导出未发生。
4. 完整回归增至 `20/20 PASS`；当前正式旧事件年龄约 2.83 小时，严格检查继续正确失败。

### 现场要求

新主事件产生后 15 分钟内完成严格验收，必须同时看到内容 `15/15`、事件新鲜度 `PASS`、严格导出快照 `15/15` 和双哈希通过。最大事件年龄增大会降低防伪强度，减小会增加现场超时风险，正式演示保持默认 `900000 ms`。

---

## 2026-07-13 答辩 Dashboard 第一屏收口

### 已完成

1. 第一屏改为 Flytotal 低空安全 AIoT 物联网主链，四段展示 ESP32-S3、融合、V4b、豆包/严格证据。
2. 当前判定统一读取 live 状态；任一主链缺口都会显示“不可作为完整现场证据”，不再由旧构建包的 0 失败项产生误导。
3. 历史工程资产、双节点和协同扩展移动到后部；后两项明确为“非计划必要内容，推荐扩展方向”。
4. 最新抓拍增加实时/历史、年龄和事件绑定状态，当前旧录像图片明确为历史且未绑定。
5. Playwright 复核桌面 `1440x900` 和手机 `390x844`：两者无横向溢出，控制台错误、页面错误、请求失败均为 0。

### 当前状态

第一屏真实显示 Node A 在线，但 V4b 离线、豆包离线、严格证据失败，因此总判定为红色。这是诚实的公共网络基线。用户回来后先让 Node A/V4b/豆包就绪，再生成新主事件；最终画面必须转为可展示状态，抓拍必须为实时且绑定该事件。

---

## 2026-07-12 第 2 步补充：豆包同事件回显与边缘安全收口

### 已完成

1. 找到云端证据链的真实性缺口：旧固件上传了事件号，但模型返回契约没有事件号；`cloud_command_source_event_id` 是成功后由本地队列号补写。因此 2026-07-08 的历史记录可证明当时 API 可达和本地命令链运行过，但不能证明云端真实回显了来源事件号。
2. 新契约要求返回 JSON 原样携带 `event_id`，CloudClient 会拒绝缺失、错号；NodeA 还要求真实返回号与当前仍活动的运行事件一致，迟到或旧事件响应安全降级。
3. `CLOUD,TEST` 改为纯预检：响应契约通过后记录 `TEST_RESPONSE_VALIDATED` 和 `no_apply=1`，不执行阈值、模式、告警或其他模型动作。
4. 未集成降落伞由“意图已记录”改为 `PARACHUTE_REJECTED_NOT_INTEGRATED`、`applied=false`、`edge_veto=1`；旧文档中的 `PARACHUTE_INTENT_LOGGED` 仅是历史固件输出，不再代表当前安全口径。
5. 高威胁时拒绝进入 `ECONOMY` 的状态由错误的 `applied=true` 修正为 `false`。
6. 离线守门增加正反检查：禁止重新出现本地队列号代填调用，测试分支内禁止调用命令执行函数，并逐分支核对两个边缘否决为 `applied=false`。

### 验收结果

```text
firmware_safety_checks: PASS (critical sections 104/104)
PlatformIO: SUCCESS
RAM 15.7%, Flash 30.1%
vision_regression_checks: PASS (21/21)
git diff --check: no whitespace errors
API/COM4/camera calls: 0
board flash: no
```

### 下一步唯一顺序

当前仅源码和本地 `.bin` 已更新，COM4 上的 NodeA 尚未刷入新契约。用户回来后：切回 W-iPhone 并打开最大兼容性 -> 停止唯一串口桥并确认 COM4 释放 -> 刷写新固件 -> 只重启一份桥接 -> 执行 `CLOUD,ENABLE,1` 和 `CLOUD,TEST` -> 确认 `validated=1,no_apply=1`、expected/response 测试号一致 -> 保持真实主事件活动直到云端返回 -> 核对 expected/response/current event 三者一致 -> 严格 `15/15` 和新鲜度通过。完成前不能把本轮离线结果称为真实云端闭环成功。

---

## 2026-07-12 第 2 步补充：COM4 进程所有权与失败零污染

### 已完成

1. NodeA 桥接新增按串口区分的操作系统跨进程锁，锁本体和 PID 元数据分离，兼容 Windows 文件锁语义；异常退出不会形成永久死锁。
2. 第二份新桥在打开 COM 和改写证据文件前直接返回 `SERIAL_OWNER_CONFLICT`，日志带持有者 PID、端口和临时锁路径。
3. 串口独占打开已移动到所有正式状态、事件、事件仓、测试结果写入之前。旧桥或 PlatformIO Monitor 占用 COM4 时，打开失败不会刷新或清空证据。
4. 新增跨进程回归：互斥、PID、释放、重获全部通过；另以假串口占用运行真实主入口，确认五类输出零创建、退出后锁释放。
5. Python 编译通过，完整回归为 `21/21 PASS`；未打开 COM4，未发送命令。

### 返场边界

当前 PID `29824` 是更新前已启动的旧桥，尚未持有新锁。用户回来后先正常停止该进程，再释放 COM4 完成固件刷写，随后只启动一份新桥并确认 `SERIAL_OWNER_ACQUIRED,port=COM4,pid=...`。新锁只能协调更新后的桥接进程，PlatformIO Monitor 等外部工具仍需关闭；但即使它们占口，新桥也不会再污染正式证据。

---

## 2026-07-12 第 2 步补充：云契约 V2 防旧固件证据

### 已完成

1. 新固件公开 `cloud_contract_version=2`、事件号强制回显、测试不执行能力和本次启动 `cloud_test_validated` 状态；无需访问 API 即可先确认刷写版本。
2. 安全预检状态只在事件号完整且一致的 `CLOUD,TEST` 成功后置 1；测试开始、断网和关闭云端都会清零。
3. 四字段从固件、串口桥、节点状态、网页事件对象贯通到导出 JSON；Dashboard live 旧板会显示 V0 并阻止就绪。
4. 严格门槛仍为 15 项，但 `cloud_event_match` 已加强为“同一返回事件号 + V2 + 回显能力 + 测试不执行 + 本次启动预检通过”。旧固件不能再靠本地补写事件号通过。
5. 反向旧契约夹具正确失败；V2 正向主门槛和严格导出均为 `15/15 PASS`，回放与双哈希通过；完整回归 `21/21 PASS`。
6. PlatformIO 构建成功，RAM `15.7%`、Flash `30.1%`；固件安全检查 `105/105` 平衡并通过。当前正式旧事件仍为预期 `3/15 FAIL` 且过期，没有自动导出。
7. 浏览器 live 反向和 mock V2 正向均验证：桌面/手机无溢出，控制台、页面和请求错误为 0；mock 即使 CLOUD READY 仍明确不可作为现场证据。

### 返场顺序

停止旧桥 -> 刷写 -> 启动唯一新桥并确认 `SERIAL_OWNER_ACQUIRED` -> 只发 `CLOUD,STATUS` -> 必须看到 V2/echo/no-apply 均正确且 `validated=0` -> 启用云端并执行 `CLOUD,TEST` -> 必须看到 expected/response 测试事件号一致、`no_apply=1`、`validated=1` -> 保持新真实事件活动直至豆包返回 -> 严格 `15/15`、新鲜度和双哈希通过。当前仍未刷写、未调用 API、未发送 COM4 命令。

## 2026-07-12 第 2 步补充：云端原始回显持久化

1. 审计发现固件已有 `CLOUD,RESULT` 请求/期望/返回事件号，但旧桥没有保存这些行，严格导出只能看到边缘二次转写后的来源事件号。
2. 新桥现在持久化 `CLOUD,STATUS`、`CLOUD,TEST`、`CLOUD,RESULT`、`CLOUD,DEGRADED`；测试事件号使用独立字段，不会覆盖当前主事件号。
3. 网页事件对象和严格导出新增 `cloud_request_event_id`、`cloud_expected_event_id`、`cloud_response_event_id`、结果来源、HTTP/ESP 状态、错误和接收时间；Dashboard 同时显示请求/期望/返回链。
4. 第 15 项 `cloud_event_match` 仍属于原 15 项，但现在直接要求：V2、本次启动安全测试、测试原始无动作返回、正式 `EVENT_OPENED` 来源、请求/期望/返回/边缘绑定/当前主事件一致、HTTP 2xx、ESP 错误 0、结果错误 `NONE`。
5. 完整正向夹具继续 `15/15 PASS`；删除原始结果字段后按预期失败；Python 和 JavaScript 语法、静态安全守门及完整回归 `21/21 PASS`。PlatformIO 构建成功，RAM `15.7%`、Flash `30.1%`。
6. 更新网页在 mock V2 下显示三事件号一致和 `EVENT_OPENED / HTTP 200`；桌面 `1440`、手机 `390` 均无横向溢出，页面错误为 0。临时 `8766` 与无头浏览器已关闭。
7. 当前正式旧事件按新门槛仍为预期 `FAIL 3/15`，同时命中事件过期、云事件不匹配和双哈希缺口，没有生成严格导出。
8. 本轮没有打开 COM4、没有调用 API、没有刷写；老桥 PID `29824` 和老网页 PID `26940` 未中断，但也未加载新 Python 逻辑。

返场顺序不变，但新桥启动后必须保留到正式导出结束。完成 `CLOUD,TEST` 后先确认 `cloud_test_result_no_apply=1` 和测试返回号，再创建新主事件；豆包返回后核对请求、期望、返回、执行绑定和当前主事件五者一致，然后运行严格 `15/15`、新鲜度与双哈希验收。

## 2026-07-12 第 2 步补充：Dashboard 云预检原始证明

1. “安全预检 PASS”和 `CLOUD READY` 现在不仅要求固件 `validated=1`，还要求桥接持久化的 `no_apply=1` 与 `A1-CLOUD-TEST` 原始返回号。
2. 固件状态通过但原始证明缺失时，页面显示 `CLOUD UNSAFE / RAW WAIT`，总判定直接指出原始无动作回显未持久化；事件详情同步使用该口径。
3. 正向 mock 为 `CLOUD READY / PASS`；删除原始测试字段的浏览器反向验证为 `CLOUD UNSAFE / RAW WAIT`。桌面 `1440`、手机 `390` 均无横向溢出，页面错误 0，完整回归 `21/21 PASS`。
4. 临时 `8766` 和无头浏览器已关闭；原桥 PID `29824`、原网页 PID `26940` 与 `8765` 未中断。本轮没有 API、COM4 或刷写操作。

## 2026-07-12 第 2 步补充：返场只读云端预检

返场时不再手工判断十多个云端字段。严格核对工具新增独立 `cloud_preflight_v1` 报告：刷写并重启新桥后先运行 `contract` 阶段，必须确认 V2 且测试/原始结果干净；执行 `CLOUD,ENABLE,1`、`CLOUD,TEST`、等待返回并再次执行 `CLOUD,STATUS` 后运行 `test` 阶段，必须确认网络、API、三个测试事件号和边缘未执行结果全部通过。两阶段只读本机 `8765`，不发命令、不访问真实 API，不替代正式新主事件 `15/15`。

离线验收：Python 语法通过，固件安全守门 `105/105`，完整回归 `21/21`，测试阶段正向夹具 `26/26 PASS`。当前旧运行态的 `contract` 预检按预期为 `7/12 FAIL`，说明它能拦截尚未刷写/重启的旧状态；PID `29824`、PID `26940` 与 `8765` HTTP 200 均未中断。返场后必须切回 W-iPhone 并打开“最大兼容性”，再按手册完成停止旧桥、刷写、启动唯一新桥和两阶段预检。

## 2026-07-12 第 2 步补充：高风险云端动作稳定策略

为降低真实模型返回无动作或不安全降级导致严格证据停在 `14/15` 的概率，系统提示词明确要求测试事件和非合作高风险主事件返回 `GENERATE_ALERT`，并禁止高风险 `NONE/ECONOMY`；请求温度固定为 `0.1`。NodeA 的测试不执行、事件号绑定、参数和威胁状态校验、未集成硬件否决均保持不变。安全守门 `105/105`、完整回归 `21/21`、PlatformIO 构建通过，Flash 为 `30.1%`。当前只证明策略已进入新固件，真实豆包响应仍需返场刷写后验证。

比赛主材料中的旧口径已同步：模型允许输出不含 `TRIGGER_PARACHUTE`；NodeA 仅保留防御性拒绝并记录 `applied=false + edge_veto=1`；Q&A 和执行摘要的 PC 完整回归更新为 `21/21`。不得再使用 `PARACHUTE_INTENT_LOGGED` 描述当前实现。

## 2026-07-12 第 2 步补充：返场服务版本与预检顺序

本次返场必须同时重启旧串口桥和旧网页服务，确保两者都加载最新云字段逻辑；PID `29824/26940` 只是当前旧进程记录，实际操作按 COM4 与 8765 所有者确认。初始预检只要求 NodeA 和 V4b 就绪，不能在云端默认关闭时先要求 `cloud_online=1`；云在线与无错误放到 `CLOUD,TEST` 和 `test` 只读预检之后判断。当前旧进程仍未被中断。

## 2026-07-12 第 2 步补充：云测试异步等待收口

`test` 只读预检支持有上限的自动轮询。返场发送一次 `CLOUD,TEST` 后，使用 `--cloud-preflight-wait-s 30`；工具只读取本机 `8765` 状态，条件达到 `26/26` 就提前返回，超时则失败，不会补发串口命令或重复调用 API。报告记录轮询次数与实际等待时间。正向异步夹具和超时反向夹具、Python 语法及完整 `21/21` 回归均通过；本轮仍未访问真实 API、COM4 或开发板。

## 2026-07-12 第 2 步补充：云预检空场基线

两阶段只读预检新增 `track_idle` 和 `event_idle`，要求测试期间 `track_active=0`、`event_active=0`、`event_id=NONE`；字段缺失也失败。这样能阻止目标过早进场造成自动主事件请求与 `CLOUD,TEST` 交叉、原始测试结果被覆盖。contract/test 条件分别增至 `14/14` 和 `28/28`；返场必须先空场通过两阶段，再让真实目标进入并生成唯一新事件。活动轨迹和活动事件反向夹具已加入，仍不接触 API、COM4 或开发板。

新鲜离线结果：空场异步夹具 `28/28 PASS`，活动轨迹和活动事件均被对应门槛拒绝，完整回归 `21/21 PASS`。当前旧 `8765` 为预期 `9/14 FAIL`，但 `track_idle/event_idle` 已通过；五个失败项均来自尚未加载的 V2 云状态。返场不要用这份旧状态继续，仍按“空场 -> 停旧服务 -> 刷写 -> 启新服务 -> `14/14` -> 一次 `CLOUD,TEST` -> `28/28` -> 目标进场”的顺序。

## 2026-07-12 第 2 步补充：云测试板端防重复

`CLOUD,TEST` 原本强制入队且云队列容量为 3，连续发送可能形成多次真实 API 请求。新固件增加已验证、测试待处理、请求执行中和队列待处理四层保护：已成功时返回 `reason=already_validated`，忙碌时返回 `reason=request_busy`，两者都不追加请求，也不清除已有成功证据。返场只发送一次测试；若看到跳过原因，不要继续连发，转而查看当前请求和预检结果。该保护尚未刷入 COM4 上的旧板。

最终离线验证：PlatformIO `SUCCESS`，RAM `15.7%`，Flash `30.1%`，固件安全守门 `108/108 PASS`，完整回归 `21/21 PASS`。新 `firmware.bin` SHA256 为 `7f8dc3d26486069b1cd8aa9c3db02dbb2e35a7e7851004ea63aeff645581d110`。未刷写、未打开 COM4、未访问 API；返场必须刷入这次构建后再验证跳过日志。

安全守门的“测试不执行”检查已改为读取 AI 云任务成功分支中的真实 `isTestRequest` 代码块，并同时要求 `TEST_RESPONSE_VALIDATED`、禁止 `applyCloudCommand`；原先取到前置状态清零分支的测试盲点已消除。

新桥只会用同时包含 `validated/no_apply/response_event_id` 的真实测试结果刷新原始接收时间；`already_validated/request_busy` 跳过日志不会改成功证明或时间。两种跳过日志的证据不变回归已通过，完整结果仍为 `21/21 PASS`。旧 PID `29824` 尚未加载这条解析保护。

## 2026-07-12 第 2 步补充：PC 双进程版本硬门槛

新桥状态公开 `serial_bridge_contract_version=2`，新网页接口公开 `web_evidence_contract_version=2`。两阶段预检同时要求这两个版本；加入版本门槛时 contract/test 为 `16/16` 和 `30/30`，后续语义策略门槛已把最终 test 标准增至 `32/32`。桥或网页任一仍是旧进程都会在真实 API 前失败。两个旧版本反向夹具和完整 `21/21` 回归通过。当前旧 PID `29824/26940` 的只读结果为预期 `9/16 FAIL`，新增失败项正是桥版本和网页版本。返场唯一有效顺序为“空场 -> 停旧桥和旧网页 -> 刷写 -> 启新桥和新网页 -> `16/16` -> 一次 `CLOUD,TEST` -> `32/32` -> 目标进场”。

隔离 HTTP 实测：当前网页代码在临时 `8876` 的 mock 节点接口返回 bridge/web 版本均为 2，验证后进程退出且端口释放；原 `8765` 未中断。完整回归仍为 `21/21 PASS`。

## 2026-07-12 第 2 步补充：豆包测试语义策略硬门槛

`test` 只读预检在原 `30/30` 基础上新增两项：测试原始结果必须为 `HIGH/CRITICAL`，且命令必须为 `GENERATE_ALERT`，因此返场标准更新为 `32/32 PASS`。这不会执行模型动作，只在真实目标进场前验证豆包是否遵守高风险告警策略；`LOW + NONE` 负向夹具会明确失败，不能继续正式主事件。

Dashboard 总览和云端详情已统一四态：`WAIT / RAW WAIT / POLICY WAIT / PASS`。审计发现并修复了总览已判 `POLICY WAIT`、详情仍可能误报 `PASS` 的不一致。隔离手机浏览器实测宽度为 viewport/client/scroll `390/390/390`；正例两处均为 `PASS`，负例两处均为 `POLICY WAIT`，页面明确显示“豆包测试策略未返回 HIGH/CRITICAL + GENERATE_ALERT”，运行异常与浏览器错误均为 0。

临时 `8878/8879/9225/9226` 端口和测试夹具均已清理，原 PID `29824/26940` 与 `8765` 保持运行。本轮仍未访问真实 API、未打开 COM4、未刷写。返场唯一顺序为：切回 W-iPhone 并打开最大兼容性 -> 空场 -> 停止旧桥和旧网页 -> 刷写新固件 -> 启动唯一新桥和新网页 -> `16/16` -> 只发送一次 `CLOUD,TEST` -> `32/32` -> 真实目标进场 -> 新事件严格 `15/15`。

## 2026-07-12 第 2 步补充：密钥 Git 防泄露硬门槛

本地 `include/secrets.h` 已确认包含 Wi-Fi 与豆包三项配置，但未被 Git 跟踪并受 `.gitignore` 保护；真实值没有写入输出。新安全守门通过 `git ls-files` 与 `git grep --cached` 扫描当前全部 `403` 个受跟踪文件的工作区和待提交索引：既拒绝 `secrets.h` 被强制加入索引，也拒绝本地 Wi-Fi 密码/API Key 被复制到任何 tracked 文件。

新增四种临时仓库回归同时证明安全正例、误跟踪文件反例、索引残留 Key 反例和历史提交残留反例。索引反例先暂存假 Key，再只清理工作区；修复前可稳定错误放行，修复后明确命中 `Git index`，且错误路径只报告符号名/路径，不泄露值。完整 PC 回归更新为 `22/22 PASS`，固件安全守门仍为 `108/108 PASS`。答辩 Q&A、执行摘要和演示手册已同步这组当前数字。

安全守门还扫描全部可达 Git 历史中的 Ark Key 形态。当前仓库命中 `0`；临时回归仓库先提交假 Key、再提交干净版本，即使当前工作区和索引都无 Key，仍会因 `reachable Git history` 被拒绝，输出不含补丁或 Key 值。

Ark Key 模式已补左边界，避免把第三方库里的 `mark-...`、`remark-...` 等普通文本误报为 Key。工作区、Git索引、Git历史三处使用同一口径；`mark-normal_identifier` 正例和真实假 Key 反例均通过预期路径。全工作区复扫只命中预期的本地 `include/secrets.h` 一处，意外副本为 0。

`firmware_safety_checks.py --require-compiled-secrets` 已把二进制存在性检查固定为返场硬门槛：当前最新 `firmware.bin` 为 `compiled_secrets: PASS (3/3)`；完整/缺项临时二进制回归分别通过和按预期失败，输出不含值。演示手册要求每次构建后、停止服务和刷写前执行该命令。这证明当前待刷二进制带有配置，但不证明 Key 仍有效或当前公共网络可访问服务。

该结果只证明密钥存储与当前 Git 工作区安全，不能证明真实 Key 仍有效或公共网络可访问豆包。返场仍必须切回 W-iPhone、打开最大兼容性，刷写后用一次 `CLOUD,TEST` 和 `32/32` 预检验证真实链路，再创建新主事件取得严格 `15/15`。

## 2026-07-12 第 2 步补充：正式高风险云语义双层硬门槛

返场后已确认实际 Wi-Fi SSID 为 `W-iPhone`、IPv4 可访问互联网、豆包目标主机 TCP 443 可达、`COM4` 已枚举。刷写前审计发现一个必须先修的证据漏洞：提示词要求高风险告警，但 `CloudClient::assess()` 只校验 JSON 与事件号便置成功；严格第 14 项也只看执行效果非空，所以非告警动作可能被误记为完整闭环。

固件现对 `A1-CLOUD-TEST`、`HIGH_RISK/EVENT` 和 `VISUALLY_CONFIRMED_DRONE` 强制要求 `HIGH/CRITICAL + GENERATE_ALERT`，否则返回策略错配并走失败/本地降级路径。严格第 14 项同步只接受 `HIGH/CRITICAL + GENERATE_ALERT + ALERT_GENERATED`，原 15 项总数不变。回归先证明 `MEDIUM + ADJUST_THRESHOLD + THRESHOLD_UPDATED` 旧门槛会误通过，再确认修复后被拒绝；安全守门固定校验执行顺序，防止以后只保留提示词而丢失代码约束。

最新离线结果：PlatformIO `SUCCESS`，RAM `15.7%`，Flash `30.1%`，固件安全守门 `108/108 PASS`，编译配置 `3/3 PASS`，完整回归 `22/22 PASS`。待刷固件 SHA256 为 `cf4ea802108a02db52951c93bb5763adce7f6e64ea19c18dfff68df2e9402774`。

尚未完成：该固件未刷入开发板，真实豆包 API 尚未由新固件调用，新同一真实事件严格 `15/15` 尚未取得。旧桥 PID `29824` 仍占 `COM4`，旧网页 PID `26940` 仍占 `8765`；下一步按实际所有者停止两者，刷写后只启动一个新桥和一个新网页，依次完成空场 `16/16`、一次 `CLOUD,TEST`、`32/32`、新主事件 `15/15`。

## 2026-07-12 第 2 步返场：板端落地与真实云预检完成

实际 Wi-Fi 为 `W-iPhone`，互联网、豆包 TCP 443 和 `COM4` 均可用。普通 PlatformIO 上传在 ESP32-S3 RAM stub 启动后稳定报 Flash 连接断流；`--no-stub flash_id` 成功读取 Flash，证明根因是 stub 交接。随后用 ROM 原生 `--no-stub --verify` 写入四段镜像，全部读回摘要一致。

新固件、新桥和新网页首次形成真实空场 `16/16 PASS`。第一次真实API已返回 `HIGH + GENERATE_ALERT` 且板端 `TEST_RESPONSE_VALIDATED`，但PC原始字段丢失，只得 `20/32`。根因是 AI 云任务用多次 `Serial.print` 拼长行时与主循环状态输出交叉。固件现把 `CLOUD,TEST/CLOUD,RESULT/CLOUD,DEGRADED` 在内存中完整组行，并连换行一次写出；安全守门禁止关键记录恢复成分段输出。

修复后构建 `SUCCESS`，RAM `15.7%`、Flash `30.1%`，安全 `108/108`、配置 `3/3`、回归 `22/22`。固件 SHA256 为 `89e4e7b7915a58e5f04a526eb4d4c4399beceed8af542bd1d4dc70e5d29b7752`，第二次逐段刷写校验通过。在原并发压力下只补做一次测试，约 10.9 秒取得真实 `32/32 PASS`，原始测试号、三事件号、HTTP 200、ESP 0、策略和时间字段完整。

当前 PID：唯一串口桥 `26120`、唯一网页 `26812`、真实摄像头/V4b `3436`。相机 source 0、1280x720、画面质量和模型均正常，但60秒内没有检测到无人机；严格 `15/15` 尚未完成。下一步必须由用户把真实无人机放入画面，先取得 `YOLO_AUTO + drone + score>=0.45`，再在明确告知舵机可能跟踪后触发唯一新事件，等待正式 `EVENT_OPENED` 云返回并立即做15项、新鲜度、双哈希与导出核验。

## 2026-07-12 第 2 步旁证：回放集成 15/15

`非计划必要内容，推荐扩展项`。用户当前在图书馆且没有无人机，因此真实无人机严格 `15/15` 保持待办。已用归档真实无人机抓拍生成明确标记的回放视频，V4b 重新达到 `YOLO_AUTO + drone + 0.89`。前两个事件分别因 ESP32 HTTP 连接失败和缺少自身匹配的成功云结果而作废，没有跨事件拼接。

第三个新事件 `A1-0000817702-0003` 取得同事件三张抓拍以及真实豆包 `HTTP 200 / ESP 0 / CRITICAL / GENERATE_ALERT / ALERT_GENERATED`，请求、期望、返回、执行和抓拍事件号一致。严格核对为主快照 `15/15 PASS`、新鲜度 `PASS`、导出快照 `15/15 PASS`、事件与视觉双哈希通过。报告位于 `captures/2026-07-13_replay_event_A1-0000817702-0003_strict_closure_report.json`，全过程舵机输出关闭，结束时轨迹和事件均已清空。

该结果只能证明回放条件下的软件同事件闭环可达，不能写成现场真实无人机证据。返场后仍需用真实无人机创建另一个全新事件并重新通过严格 `15/15`，然后执行 2026-07-13 第 4 步类别、距离和长稳外场矩阵。

## 2026-07-13 第 4 步返场前准备：外场试验证据包

原轨迹采集器只能证明 LD2450 七列数据，无法强制绑定10/30/50米视觉与 LD2451 试验的目标、距离来源、动作、环境和原视频。现新增只读 `tools/field_trial_recorder.py`：每个唯一会话持续保存 API 原始状态并形成摘要，明确区分 `trial_valid`、`performance_pass/outcome` 和 `evidence_complete`。失败、误锁、黑帧、状态中断和缺视频不会被记录成功掩盖，重复会话不能覆盖；视频转入电脑后可按同一会话补 SHA256。

该工具不打开 COM4、不发送串口命令、不改阈值或主链。该阶段 TDD 红灯与正反夹具完成时回归为 `24/24 PASS`，后续外场总门扩充后当前为 `25/25 PASS`。真实无人机、真实距离和20分钟长稳仍未执行，全部矩阵状态保持 `PENDING`；返场时先完成全新真实事件严格 `15/15`，再用该入口逐格采集。

真实 `8765` API 的初次回放烟测暴露文件视频可被误记为外场来源，现已修成双层硬拒绝：记录器把非数字 source 的采样置为无效，出发预检把回放固定为 `NO-GO 15/16 / physical_camera_source`。新增 `field_collection_preflight.py` 后，真实 USB 摄像头 source `0` 达到 `GO 16/16`；停止摄像头后最新状态重新为 `NO-GO 15/16 / vision_runtime_fresh`。物理摄像头 GO 报告已保存，当前板端为 `VISION_LOST`，舵机、轨迹和事件均关闭或空闲。

## 2026-07-13 第 4 步返场前准备：外场总门与长稳加固

用户明确“现场”是去采集真实无人机，并希望一次外场出行尽量采齐国一证据。现将核心任务固定为 27 条距离报告：无人机、人物、车辆在 10/30/50 米各 3 次；另加静态杂波和正常人车环境各 20 分钟。`field_evidence_gate.py` 只读汇总全部试验，要求独立视频哈希、正式模型标签和 SHA256、物理摄像头、有效原始样本与实际长稳时长；缺格、错模型、重复视频、损坏报告、误锁或中断均保持 `NO-GO`，并返回下一批缺项。

`field_trial_recorder.py` 现在每次试验先核验冻结 V4b SHA256，错误模型不占用会话号；样本逐条刷新、每秒强制落盘、结束再次落盘，降低 20 分钟记录时的 I/O 抖动并保存真实经过时长。完整正例 27+2 为 `GO 22/22`，错模型、1199 秒长稳和损坏报告反例均被拒绝；Python 编译和完整回归为 `25/25 PASS`。

当前真实目录仍为 0 份外场报告，所以矩阵门为 `NO-GO 3/22`、距离剩余 27、长稳剩余 2。返场必须先恢复物理摄像头并取得 `same-event` 预检 GO，用全新真实无人机事件取得严格 `15/15`，再完成矩阵、转入并 finalize 独立视频；矩阵 `GO 22/22` 后还要取得最终 `mission-final GO 25/25`。该流程能显著降低二次返场概率，但不能把尚未发生的实测或评委奖项写成必然结果。

## 2026-07-12 第 2 步与 2026-07-13 第 4 步合并总门

历史回放严格报告虽然在旧规则下达到 15/15，但事件视觉证据哈希未包含 camera source，无法由机器证明是物理摄像头。现已把 `source/physical_camera_source/capture_backend` 写入 `vision_evidence_v1` 并参与 SHA256；严格 15 项数量不变，其中视觉有效性要求数字物理 source，detector 就绪要求正式 V4b 标签。物理 source 0 正例继续通过，MP4 全字段正例固定失败，严格导出回放哈希一致。

外场矩阵门另新增 `mission-final` 模式，将矩阵 22 项、本次 same-event 预检、真实严格主快照/导出 15/15 和 8 小时同场时间窗合成最终 `25/25`。它拒绝历史回放、distance-only 预检、窗口外报告和跨日期拼接；最终报告为 `captures/latest_field_mission_final_report.json`。完整回归仍为 `25/25 PASS`。

当前网页 PID `26812` 仍是变更前进程，尚未加载来源入哈希；返场前需由正式入口重启唯一网页。当前真实报告为 0，矩阵 `NO-GO 3/22`，所以最终门保持 NO-GO。原交接中“GO 22/22 即结束外场”的表述升级为：矩阵 22/22 仅证明距离与长稳齐全，必须再取得 `mission-final GO 25/25` 才能结束整次外场任务。

## 2026-07-13 外场冻结：重启舵机安全根因闭环

真实预检暴露板端近期重启后 `servo_enabled=1`。根因有三层：全局初值默认开启、`RESET` 重新开启、TrackingTask 又无条件直接 attach 两路 PWM。先用统一收件箱关闭当前输出，再以 TDD 将三条约束写入固件安全守门：上电初值关闭、RESET 后关闭、TrackingTask 禁止绕过单一输出门直接 attach。

最终固件 SHA256 为 `c5f7e0529b385d322a35578bf1febed329104829d23567820889f7f6ea7fb2e0`；PlatformIO `SUCCESS`，RAM `15.7%`、Flash `30.1%`，编译配置 `3/3 PASS`。ROM no-stub 四段刷写并校验后，真实上电 `servo_enabled=0 / servo_attached=0`，统一收件箱执行一次 `RESET` 后仍为 `0/0`。当前唯一桥 PID `36268`、网页 PID `29592`；轨迹和事件为空。

当前 distance 预检为 `NO-GO 15/16`，只缺 `vision_runtime_fresh`，因为真实摄像头未启动。RESET 已清除云测试验证，返场顺序是：启动真实摄像头、空场确认、重新完成一次 CLOUD,TEST 32/32、运行 same-event 预检作为 8 小时任务起点。矩阵仍为 0 份、`NO-GO 3/22`，最终 mission-final 仍为 NO-GO，不能宣称已取得真实国一证据。

## 2026-07-13 官方必备项补漏：同采样实机融合与最终 26/26

乐鑫赛题明确要求至少一种传感器数据融合。复核发现旧严格 `15/15` 与旧最终 `25/25` 都未强制要求真实雷达和物理视觉在同一采样点融合，Dashboard 的视觉/云证据完整并不能替代该必备项。

外场记录器现逐点保存测试模式和增强融合字段，只有物理 V4b 自动锁定、LD2450 活跃确认、测试模式关闭、增强融合开启、MID/HIGH 融合与真实活动事件同时成立才计入 `physical_fusion_sample_count`，并保存对应事件号。最终门新增 `real_sensor_fusion_evidence`，要求该事件号与严格 `15/15` 事件号一致；报告 schema 升级为 V2，最终收工数字由 `25/25` 改为 `26/26`。

出发预检前移同一限制：固件上电/RESET 后仍默认基础兼容模式，正式任务先经统一收件箱发送 `FUSION,ENABLE,1`。distance 预检现为 `17/17`，same-event 预检为 `18/18`。红灯证明旧门会放过无融合任务；修复后完整夹具 `GO 26/26`，无融合任务和融合关闭预检均稳定失败，完整 PC 回归 `25/25 PASS`。

返场唯一顺序更新为：启动物理摄像头 -> 空场开启 `FUSION,ENABLE,1` -> `CLOUD,TEST 32/32` -> same-event `18/18` -> 用真实无人机产生同一事件实机融合样本和严格 `15/15` -> 完成27条距离与2条长稳 -> matrix `22/22` -> mission-final `26/26`。真实无人机未到场前该项仍为 PENDING。

当前真实空数据基线已重跑：distance `NO-GO 15/17`，仅缺实时相机与增强融合；matrix `NO-GO 3/22`；mission-final `NO-GO 3/26`，明确新增缺项 `real_sensor_fusion_evidence`。这些 NO-GO 是预期保护，不是工具回退。

## 2026-07-14 第 4 步稳定性收口：启动编号、复位原因与中途重启拒绝

真实运行曾观察到板端毫秒时钟从约 513 秒回到约 71 秒，但旧状态没有复位原因，无法判断是拔插、USB 下载复位、看门狗、崩溃还是供电异常；旧外场记录也不能证明一段数据没有跨过重启。该缺口直接影响一次返场取证的可靠性，归入 2026-07-13 第 4 步，不作为扩展项。

固件现输出唯一 `boot_id`、RTC 启动计数、有效复位原因、ESP 高层原因、ESP32-S3 原始原因码和运行时长。串口桥记录启动切换次数与主机观察时间；预检要求当前启动稳定至少 15 秒；单次试验若观察到多个启动编号或运行时长倒退，整段固定为无效，矩阵总门同时拒绝缺少启动证明的旧报告。主控制链和舵机策略未改。

第一次实机烧录确认 ESP 高层接口对 USB 下载复位返回 `UNKNOWN`，原始码为 `21`。第二轮实现使用 ESP32-S3 ROM 原因补全，最终真实输出为 `reset_reason=USB_UART / reset_reason_raw=21`，证明这是下载器复位而非看门狗、崩溃或掉电。最终固件 SHA256 为 `e352963b749a6196ea4e308b589421c31b64731e4305febc5e1364def22893e3`；PlatformIO `SUCCESS`，RAM `15.7%`、Flash `30.2%`，安全 `108/108`、配置 `3/3`、完整回归 `25/25`。

当前唯一串口桥 PID `40140`、网页 PID `29592`、物理视觉桥 PID `40632`，视觉桥按 source `0` 和正式 V4b 启动。当前启动编号 `A1-00000001-A9EC1B8A`、启动切换计数 0，舵机 `0/0`。距离预检真实 `GO 17/17`；随后同一启动完成真实豆包 `HTTP 200 / TEST / GENERATE_ALERT / TEST_RESPONSE_VALIDATED`，same-event 预检真实 `GO 18/18`。

云测试后进行了 `1020.8` 秒连续观察，共读取 68 次真实状态。启动编号未变化，运行时长从 `371236 ms` 增长到 `1378088 ms`，`node_boot_change_count=0 / reset_observed=false`；融合、云验证和三份生产进程保持稳定，舵机 `0/0`。此前约 15 分钟后板端时钟回落的现象未复现。

仍未完成：全新物理无人机同事件严格 `15/15`、同事件实机融合、27 条距离报告和两条 20 分钟长稳。下一步只能在真实无人机到场后继续，不能用当前空场 GO 或历史回放替代。
