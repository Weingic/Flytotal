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
