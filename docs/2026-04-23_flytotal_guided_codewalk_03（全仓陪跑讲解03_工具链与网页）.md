# Flytotal 全仓陪跑讲解 03：工具链与网页

这一讲专门解决一个很容易让人误会的问题：

“为什么 `tools/` 里会有这么多 Python 脚本和网页文件？它们是不是杂乱的边角料？”

结论先说：

不是。

这些文件共同承担的是“系统外部支撑层”，让固件从“能跑”变成“能联调、能观察、能验证、能交付”。

---

## 1. 先把工具链分成 6 类

```text
输入模拟层
    track_injector / rid_broadcast_simulator / track_scenarios

桥接层
    node_a_serial_bridge / vision_bridge

展示层
    vision_web_server / vision_dashboard

预检与启动层
    preflight / startup_helper

验收与一致性层
    acceptance_* / consistency_* / contract_* / web_consistency_*

统计与交付层
    false_alarm / e2e_latency / closure / evidence_hash / delivery_bundle / report_summary
```

如果按这个分类去看，工具链就不乱了。

---

## 2. 输入模拟层：没有稳定输入，就没有稳定联调

### 2.1 `tools/track_injector_轨迹注入器.py`

### 代码事实

这是当前工具链里最核心的输入模拟脚本之一。  
从函数名就能看出它的职责很重：

- 读取 `track_scenarios.json`
- 发送轨迹点和控制命令
- 后台观察串口输出
- 构建事件历史
- 运行多种 suite
- 生成 session payload
- 生成验收快照
- 生成联合证据 payload

里面最关键的角色包括：

- `SuiteCheck`
- `SerialObserver`
- `run_standard_acceptance_suite`
- `run_single_node_realtime_v1_suite`
- `run_risk_event_vision_chain_v1_suite`
- `run_rid_identity_chain_v1_suite`

### 设计理解

为什么要有轨迹注入器？

因为真实雷达场景有 3 个问题：

1. 不可重复
2. 不可控
3. 难以自动化

而联调最需要的是：

- 指定某条轨迹
- 指定某个 RID 状态
- 指定某个步骤顺序
- 然后反复跑，观察系统是否稳定

### 设计推断

这个脚本体现的是“把联调流程脚本化”的思路。  
它已经不只是测试工具，而是把一轮演示/验证流程编程化了。

### 2.2 `tools/track_scenarios.json`

### 代码事实

这个文件给注入器提供场景配置。

### 设计理解

为什么场景要数据化，而不是写死在 Python 里？

因为轨迹本质上是“测试输入集”。  
把它拆成 JSON，才方便：

- 复用
- 对比
- 固化基线
- 非程序人员也能看懂

### 2.3 `tools/rid_broadcast_simulator_身份广播模拟器.py`

### 代码事实

这个脚本负责生成 RID 文本广播消息。

### 设计理解

它解决的是：在没有真实身份广播设备时，如何驱动 RID 链路进入不同状态。

### 设计推断

它说明身份链路不是只靠文档假想，而是已经被纳入可模拟输入的一部分。

---

## 3. 桥接层：把板端世界翻译成主机世界

### 3.1 `tools/node_a_serial_bridge_NodeA串口桥接.py`

### 代码事实

这个脚本会：

- 读取设备串口输出
- 解析前缀和 `key=value`
- 把多种输出归一到统一 JSON 字段
- 维护运行时状态
- 构造中心侧 payload
- 保存事件历史与事件仓
- 记录测试结果
- 根据需要向中心服务上报

关键函数包括：

- `parse_prefix_and_fields`
- `normalize_fields`
- `evaluate_status_consistency`
- `build_event_record`
- `append_event_store_record`
- `update_test_result_monitor`
- `update_status_from_line`

### 设计理解

为什么桥接层这么重要？

因为板端说的是串口文本协议，主机工具和网页更适合吃 JSON。  
桥接层就是协议翻译器：

```text
串口文本
    ->
统一 JSON 状态
    ->
网页 / 验收 / 中心接口
```

### 设计推断

它体现的是“不要让每个工具都直接去解析串口”的设计。  
一旦有桥接层，后续所有工具都围绕同一份 JSON 语义工作，系统耦合度会低很多。

### 3.2 `tools/vision_bridge_视觉桥接.py`

### 代码事实

这个脚本是视觉侧的主桥接器，做的事非常多：

- 打开摄像头
- 选择 OpenCV tracker
- 跟踪 ROI
- 构造 `VisionSnapshot`
- 保存连续视觉日志 CSV
- 记录抓拍元数据 CSV
- 从节点状态文件读取 `risk_level`、`event_id`、`gimbal_state`
- 根据策略决定是否抓拍
- 绘制叠加框和引导框
- 输出最新视觉状态 JSON

关键类包括：

- `VisionSnapshot`
- `CaptureRecord`
- `NodeRuntimeSignals`
- `GimbalSignals`
- `CsvVisionLogger`
- `CaptureMetadataLogger`
- `VisionStateReporter`

### 设计理解

为什么视觉桥接不直接并进固件？

因为视觉这条链路天然更适合跑在主机侧：

- OpenCV 依赖重
- 摄像头输入在主机侧更方便
- 图像保存和叠加在主机侧更容易

但视觉又必须理解板端状态，比如：

- 当前是不是高风险
- 当前事件 ID 是什么
- 现在是否允许抓拍

所以视觉桥接本质上是“主机视觉 + 板端状态”的连接点。

### 设计推断

它体现的是一种很实际的混合系统思路：

- 强实时状态判断放板端
- 重资源视觉和文件处理放主机

这比把所有东西都塞进 ESP32 更现实。

---

## 4. 展示层：系统不仅要工作，还要能被人看懂

### 4.1 `tools/vision_web_server_视觉网页服务.py`

### 代码事实

这是整个主机侧的 API 层。  
它负责：

- 提供 HTTP 服务
- 读取状态 JSON、事件 JSON、抓拍 CSV、导出文件
- 整理 captures payload
- 整理 node brief/fleet payload
- 构造 event object
- 管理 active event payload
- 写出事件导出 payload
- 整理 test session/test results
- 提供 session timeline
- 兼顾 mock 模式
- 计算和附加 `evidence_hash`

### 设计理解

为什么还需要一个 web server，而不是脚本直接给网页喂文件？

因为网页最舒服的消费方式不是散落文件，而是稳定 API。  
这样网页层就不需要关心：

- 数据从哪个文件来
- 文件名是否变化
- 是 mock 还是真实
- 记录如何去重和归一

### 设计推断

这个文件本质上是“主机编排层”。  
如果说 `src/main.cpp` 是固件编排层，那么 `vision_web_server` 就是主机侧的编排层。

### 4.2 `tools/vision_dashboard.html`

### 代码事实

这是一个本地联调看板页面。  
从结构上看，它包含：

- 顶部 hero 区
- 多张状态卡片
- 抓拍展示区
- 数据表格和详情区域

页面风格不是默认模板，而是有明确的视觉语言：

- 米色暖底
- 橙绿双强调色
- 玻璃化 panel
- 大标题和较强层次

### 设计理解

为什么要专门做一个页面？

因为很多状态如果只在串口文本里看，会非常费脑。  
一个联调看板至少能帮助解决 3 件事：

1. 当前系统活没活着
2. 当前目标处在哪个阶段
3. 当前证据和抓拍是否已经产生

### 设计推断

这个页面说明项目已经进入“面向演示和答辩表达”的阶段。  
它不是简单 debug panel，而是“把复杂内部状态翻译给人看”的界面。

---

## 5. 预检与启动层：先确认环境，再开始跑

### 5.1 `tools/preflight_411_环境预检.py`

### 代码事实

这个脚本会检查：

- Web health
- TCP 端口
- 串口是否存在
- USB 摄像头就绪情况
- 视觉运行时状态文件

### 设计理解

为什么需要 preflight？

因为很多联调失败根本不是业务逻辑错误，而是：

- 相机没准备好
- 网页服务没起来
- 串口没连上
- JSON 文件陈旧

### 设计推断

这代表项目从“靠人盯”转向“流程化启动检查”。

### 5.2 `tools/startup_helper_411_单节点启动助手.py`

### 代码事实

它负责串联：

- preflight
- suite 顺序解析
- 启动前状态整理

### 设计理解

它解决的是“启动动作太多、容易漏一步”的问题。

### 设计推断

当一个项目需要 helper，说明它已经超过“手敲两条命令就能稳跑”的规模了。

---

## 6. 验收与一致性层：把“我觉得可以”变成“系统证明可以”

### 6.1 `tools/acceptance_flow_411_单节点闭环验收流程.py`

### 代码事实

它会：

- 找到相关工具脚本
- 等待 web health ready
- 跑单个步骤
- 串联 preflight、track injector、closure check 等环节
- 输出统一报告

### 设计理解

它不是单个测试，而是验收编排器。  
解决的问题是：一轮验收要经过很多工具，必须有统一顺序和统一报告。

### 6.2 `tools/acceptance_auto_411_快检全检自动验收.py`

### 代码事实

它会在 quick / full 两种模式之间调度，最后产出合并报告。

### 设计理解

为什么要分快检和全检？

因为开发时需要快反馈，交付时需要全覆盖。  
这是非常典型的工程分层验证思路。

### 6.3 `tools/consistency_check_一致性核对.py`

### 代码事实

它会加载证据 JSON，检查字段和 hash 一致性，还带 mock self test。

### 设计理解

这类脚本不是测业务是否聪明，而是测“数据结构是否可信、前后是否一致”。

### 6.4 `tools/uplink_packet_contract_check_报文契约核对.py`

### 代码事实

它验证状态和事件 payload 是否缺字段、是否符合契约，并更新验收快照。

### 设计理解

这是把“串口/JSON 输出”当成正式接口来管理，而不是临时调试文本。

### 6.5 `tools/node_web_consistency_check_NodeA网页一致性核对.py`

### 代码事实

它比较本地 payload 和网页接口字段是否一致。

### 设计理解

这个脚本解决的是：桥接正确，不代表页面展示正确。  
中间多了 API 层和前端层，一定要再核一层。

---

## 7. 证据、统计与交付层：结果要能留痕、能复盘、能打包

### 7.1 `tools/single_node_evidence_closure_check_单节点证据闭环核对.py`

### 代码事实

它会：

- 读取 JSON 和 CSV
- 选取最新事件
- 检查视觉证据是否闭环
- 拉取网页端数据辅助确认

### 设计理解

所谓“闭环”，不是只有事件发生，还要能证明：

- 事件在系统里留存了
- 视觉抓拍命中了
- 页面和导出能找到它

### 7.2 `tools/evidence_hash_证据链哈希.py`

### 代码事实

负责提取关键字段，计算并验证证据 hash。

### 设计理解

这一步的目的不是密码学炫技，而是让证据对象具备“篡改可发现”的能力。

### 7.3 `tools/delivery_bundle_readiness_check_交付包就绪核对.py`

### 代码事实

它检查：

- suite payload
- evidence payload
- contract payload
- snapshot payload

最终构建交付报告。

### 设计理解

这说明项目已经在考虑“打包交付”而不只是本地联调。

### 7.4 `tools/false_alarm_baseline_误报率基线测试.py`

### 代码事实

它从事件文件和事件仓里收集事件，去重后统计误报基线。

### 设计理解

误报是风险系统最核心的工程指标之一。  
这个脚本代表项目开始从“功能是否存在”走向“指标是否可信”。

### 7.5 `tools/e2e_latency_stats_E2E延迟统计.py`

### 代码事实

它抽取注入点和事件输出，配对后统计端到端时延。

### 设计理解

说明系统开始关心链路性能，而不是只关心功能开关。

### 7.6 `tools/real_radar_scenario_checker_实机场景核对.py`

### 代码事实

它读取状态样本，评价持续目标、目标丢失等实机场景。

### 设计理解

模拟和自动注入很重要，但最后仍要回到真实场景。

### 7.7 `tools/real_radar_report_summary_实机报告汇总.py`

### 代码事实

负责汇总多份实机报告，形成总结。

### 设计理解

说明项目已经有“跑多次、做汇总”的需求，而不是只看一次实验。

---

## 8. 设备与辅助检查工具：保证链路可启动

### 8.1 `tools/usb_camera_readiness_check_USB摄像头就绪核对.py`

### 代码事实

它负责：

- 检查 OpenCV tracker 能力
- 选择 capture backend
- 试探摄像头打开是否成功
- 输出报告

### 设计理解

视觉链路最常死在环境层，而不是业务层。  
所以先把设备就绪单独检查出来，非常合理。

### 8.2 `tools/esp32_single_board_test_单板测试.py`

### 代码事实

一个更轻量的串口读写测试脚本，用于快速发命令和读回显。

### 设计理解

它像是早期单板联调的最小工具。

---

## 9. 日志与会话工具：给其他脚本提供公共基础

### `tools/session_log_utils_会话日志工具.py`

### 代码事实

这个文件提供会话日志相关通用函数，例如：

- 解析串口前缀
- 解析字段
- 构建串口记录
- 从 payload 推导 session log 路径
- 追加 session 事件

### 设计理解

这是典型的“共享基础设施”脚本。  
没有它，多个工具会重复实现一遍日志解析。

### 设计推断

说明工具链已经开始形成“内部公共库”。

---

## 10. Git 同步脚本：不属于业务，但属于协作链

对应文件：

- `tools/git_integration_sync.ps1`
- `tools/git_integration_sync_mac.sh`
- `tools/git_integration_pull_after_win.sh`

### 代码事实

这些脚本用于不同系统环境下的同步和拉取流程。

### 设计理解

虽然它们不参与主业务，但它们是项目协作基础设施的一部分。  
当一个项目跨 Windows / macOS 环境，脚本化同步能减少人为失误。

---

## 11. 为什么这些脚本会越来越多

你可以把工具链理解成项目复杂度增长后的自然产物：

### 当只有板端时

你只需要：

- 固件
- 简单串口输出

### 当需要重复联调时

你会长出：

- 注入器
- 串口桥接
- 状态文件

### 当需要演示和答辩时

你会长出：

- 网页服务
- 联调看板
- 抓拍导出

### 当需要正式验收和交付时

你会长出：

- 预检
- 自动验收
- 契约核对
- 一致性核对
- 证据 hash
- 统计脚本

所以脚本变多，不一定代表架构失控。  
在这个仓库里，更像是系统能力从“跑起来”走向“证明自己”的自然结果。

---

## 12. 这一讲你最该记住什么

你最该记住的是：

1. `tools/` 不是杂物堆，而是系统外部支撑层。
2. 串口桥接负责把板端世界翻译成主机世界。
3. 视觉桥接负责把摄像头和事件链连接起来。
4. 网页服务和看板负责把复杂状态翻译给人看。
5. 验收、契约、一致性、统计脚本负责把“感觉能用”升级成“可证明能用”。

如果你能把这 5 句话讲出来，你对这个仓库的理解就已经不是“文件太多我看不懂”，而是“我知道每类文件为什么存在”了。
