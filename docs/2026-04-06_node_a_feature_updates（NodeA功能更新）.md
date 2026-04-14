# 2026-04-06 NodeA 功能更新

## 1. 本次推进位置
本次属于 `2026-04-07` 的收尾修正。

目标不是改主链能力，而是把事件关闭后的“留痕语义”补稳定，避免验收时看到：
- 真正的关闭原因被后续普通状态覆盖
- `LASTEVENT` 在 `UPLINK,OFF` 时拿不到结果
- `RESET` 后最近事件不能正确保留

## 2. 本次改动文件
- `src/main.cpp`
- `tools/track_injector_轨迹注入器.py`
- `docs/2026-04-06_node_a_feature_updates（NodeA功能更新）.md`

## 3. 本次实际修正内容

### 3.1 `UPLINK,OFF` 时也会缓存最近事件
之前 `emitCloudEvent(...)` 里如果 `UPLINK` 输出关闭，会直接返回。

这会带来一个问题：
- 事件在系统里真实发生了
- 但因为不上行打印，`LASTEVENT` 也不会被缓存

现在已经调整为：
- 先缓存 `LASTEVENT`
- 再决定是否打印 `UPLINK,EVENT`

这样即使现场验收时用了：
- `DEBUG,OFF`
- `UPLINK,OFF`

也仍然可以通过 `LASTEVENT` 看最近一次事件结果。

### 3.2 终态关闭原因保护
这次新增了终态关闭原因保护，以下关闭原因会被视为“终态关闭”：
- `RISK_DOWNGRADE`
- `TRACK_LOST`
- `RESET`

一旦当前事件对象已经带有这类关闭原因，后面再出现普通状态变化时，就不应该把它改掉。

这次主要防的是下面这种现象：
- 事件本来已经因为 `TRACK_LOST` 关闭
- 但后面又来了一个 `HUNTER_STATE`
- 最终 `LASTEVENT` 只剩下 `HUNTER_STATE`

### 3.3 `RESET` 路径补了显式最近事件缓存
之前 `RESET` 后的关闭语义不稳定，原因是：
- 复位会清状态
- 后续任务还会继续跑状态流转
- 容易把刚才真正想留下的“复位关闭”挤掉

现在在 `RESET` 路径里增加了显式缓存逻辑：
- 先拿到复位前的事件快照
- 再执行复位
- 如果复位前存在有效事件，就把它作为 `EVENT_CLOSED + RESET` 写入最近事件缓存

### 3.4 `4.7` 验收脚本继续标准化
`tools/track_injector_轨迹注入器.py` 已用于替代手工串口连敲。

当前推荐做法：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --validate-47
```

这个模式会自动执行：
- `RESET`
- `DEBUG,OFF`
- `UPLINK,OFF`
- 多次 `TRACK`
- `RID` 切换
- `RISK,STATUS`
- `EVENT,STATUS`
- 回落 / 丢失 / 复位验证

## 4. 当前验证结论
`4.7` 这个阶段最重要的结论是：

- 主链风险升级已经通过
- 事件对象打开已经通过
- `current_event_close_reason=RISK_DOWNGRADE` 已正确出现
- `current_event_close_reason=TRACK_LOST` 已正确出现

也就是说：
- **事件对象本身的关闭语义已经成立**

当前剩余的已知尾巴是：
- `LASTEVENT` 最近事件缓存仍不够稳定
- 在部分路径下仍会出现 `LASTEVENT,NONE`
- 或者被普通状态如 `HUNTER_STATE` 覆盖

当前建议：
- 不再继续在 `4.7` 这个点上长期消耗
- 把它记录为已知问题
- 后续进入 `4.8` 时继续推进标准化测试和操作体验

## 5. 编译与检查情况
本次修改后已完成：

- 固件编译通过
```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run
```

- Python 脚本语法检查通过
```powershell
python -m py_compile tools/track_injector_轨迹注入器.py
```

## 6. 可操作性增强
为了降低后续联调时“命令记不住、输出太长看不懂”的问题，本次还新增了两项轻量增强：

- 固件新增 `BRIEF`
  - 用一条短输出显示当前最核心的状态
  - 重点只保留：主状态、轨迹、风险、事件、关闭原因、目标坐标

- 新增速查表文档
  - 文件：`docs/10serial_command_quick_reference（串口命令速查表）.md`
  - 用途：以后手工联调时，不再靠记忆回想命令

推荐以后手工查看优先使用：

```text
HELP
BRIEF
RISK,STATUS
EVENT,STATUS
```

推荐以后先执行：

```text
DEBUG,OFF
UPLINK,OFF
```

这样串口输出会清爽很多，更适合现场联调。

## 7. 继续推进：进入 4.8 标准化测试入口

本轮继续推进的位置，已经从 `4.7` 主链收尾，转入 `2026-04-08` 的标准化测试阶段。

这次没有继续扩主链逻辑，而是优先增强：

- `tools/track_injector_轨迹注入器.py`
- `tools/session_log_utils_会话日志工具.py`

目标是把原来“会发轨迹”的脚本，升级成“能直接做标准验收”的脚本。

### 7.1 新增标准验收套件模式

现在轨迹注入脚本支持：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite standard_acceptance
```

这个模式不再只是盲发命令，而是会自动执行一整套标准步骤：

- `RESET`
- `DEBUG,OFF`
- `UPLINK,OFF`
- `LASTEVENT,CLEAR`
- 注入确认轨迹
- 切换 `RID`
- 自动查询 `BRIEF`
- 自动查询 `RISK,STATUS`
- 自动查询 `EVENT,STATUS`
- 自动查询 `LASTEVENT`

### 7.2 现在脚本会自动给 PASS / FAIL

这次最关键的变化不是“多发了几个命令”，而是：

- 脚本会抓取串口返回行
- 自动解析字段
- 按步骤校验是否满足预期
- 直接打印：
  - 哪一步通过
  - 哪一步失败
  - 失败时是哪一个字段不符合预期

当前标准套件重点覆盖：

- 复位后空闲基线是否正确
- 风险事件是否成功打开
- `RID,OK` 后是否触发 `RISK_DOWNGRADE`
- `TRACK,CLEAR` 后是否留下 `TRACK_LOST`

### 7.3 现在更适合做现场验收和复测

这次改完后，脚本从“操作工具”更接近“验收工具”了。

好处是：

- 不用靠人脑记每一步该查什么
- 不用肉眼在长串口输出里手动找字段
- 一轮跑完就能知道当前主链是否还保持稳定
- 后续接 USB 摄像头之前，也有一套固定基线先守住

### 7.4 兼容原有 4.7 验收方式

原有命令仍然保留：

```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --validate-47
```

只是现在它内部也会走同样的自动判定逻辑，不再只是“执行动作”，而是会给出更明确的通过/失败结果。

### 7.5 套件跑完后会留下结构化验收报告

这次继续补强后，标准套件不只是终端里打印几行 `PASS / FAIL`，还会在最终会话 JSON 里附带一份结构化汇总。

重点包括：

- 总检查数
- 通过数
- 失败数
- 通过项名称
- 失败项名称
- 失败原因
- 对应触发命令
- 对应串口原始返回行

这样后面如果要继续做：

- 更清楚的复测记录
- 网页侧结果展示
- 自动留档
- 多轮测试结果对比

就不需要重新从终端文本里二次抠信息了。

### 7.6 套件报告已接入本地看板与结果汇总链

为了让标准化验收结果不仅“在终端可看”，这次又补了两处接入：

- `tools/vision_dashboard.html`
- `tools/node_a_serial_bridge_NodeA串口桥接.py`

具体效果：

- 测试场景卡片新增套件字段：
  - 套件名称
  - 套件步骤
  - 套件检查通过/失败
  - 套件失败项
- 联调时间线新增套件事件语义：
  - `suite_started`
  - `suite_check`
  - `suite_finished`
- 测试结果历史展开详情新增：
  - 套件摘要
  - 套件失败项明细
- 串口桥接输出的 `latest_test_result.json / latest_test_results.json` 现在会透传：
  - `suite_report`
  - `suite_failed_checks`
  - `suite_passed / suite_failed / suite_step_total`

这样后续你在网页里就能直接看出：

- 这一轮是哪个套件
- 总共检查了多少项
- 哪几项没过以及失败原因

不需要再手动翻终端文本。

### 7.7 失败项可一键跳到时间线并高亮

为了让排查更快，这次把“套件失败项”继续做成可点击跳转：

- 在“测试结果历史”的展开详情里，失败项会显示为按钮
- 点击后会自动切到对应会话时间线
- 自动定位并高亮对应 `suite_check` 记录

这样做的目的很直接：

- 从“看到失败项名称”
- 直接进入“看到当时那条原始检查记录”

中间不需要再手动筛选或反复滚动查找。

### 7.8 时间线新增“选中检查详情”固定视图

在 7.7 的基础上继续推进了一步：  
现在跳转并高亮后，页面会在时间线区域固定展示一块“选中检查详情”，包含：

- 选中检查名
- 检查结果（PASS/FAIL）
- 检查时间
- 触发命令
- 失败原因
- 备注
- 原始串口行

这样你不需要在高亮行和历史详情之间来回切换，定位到失败项后就能直接看到这条检查的关键上下文。

### 7.9 前端渲染函数去重收口

继续推进时做了一个低风险收口：

- 清理 `tools/vision_dashboard.html` 中重复存在的 `renderTestResults()` 旧实现
- 保留当前完整的新实现（包含展开详情、会话跳转、失败项跳转）

目的：

- 避免“同名函数后定义覆盖前定义”带来的隐性维护风险
- 降低后续继续改测试结果表时的误改概率

### 7.10 新增失败检查“复制/导出”动作

在时间线的“选中检查详情”区域继续补了两个实用动作：

- `复制选中检查`
- `导出本轮失败摘要`

复制内容包含：

- 检查名
- PASS/FAIL
- 触发命令
- 失败原因
- 备注
- 原始串口行

导出内容包含当前会话全部失败 `suite_check` 明细，每条都带：

- 时间
- 检查名
- 命令
- 失败原因
- 备注
- 原始串口行

这样你在联调现场可以直接把失败上下文快速发给协作方，不需要再手工整理。

### 7.11 新增“一键复制失败清单 / 导出完整报告”

在 7.10 的基础上继续补了两项动作：

- `复制本轮失败清单`
- `导出本轮完整验收报告`

现在动作区共支持：

- 复制选中检查（单条）
- 复制本轮失败清单（全部失败项）
- 导出本轮失败摘要（失败项文件）
- 导出本轮完整验收报告（通过项 + 失败项）

其中“完整验收报告”会包含：

- 会话信息
- 总检查数
- 通过数
- 失败数
- 通过项列表
- 失败项详细上下文

这样在最后统一联调测试时，结果可以直接落地成结构化文本，不需要二次手工汇总。

### 7.12 会话摘要已接入 suite_finished 结论

继续推进后，`session_logs/*.jsonl` 里的 `suite_finished` 事件现在会被服务端会话摘要读取并聚合。

具体新增摘要字段：

- `suite_name`
- `suite_passed`
- `suite_failed`
- `suite_result`（PASS / FAIL / NONE）

看板“联调时间线”区域同步新增了“套件”摘要芯片，显示：

- 套件名
- 套件结论
- 通过/失败计数

这样即使某轮没有产出 `test_result`，也能直接看出该会话的套件验收结论。

### 7.13 最终一次性联调测试清单（统一回归版）

为了满足“功能都更新完再一起测”，这里给出一轮跑完的固定清单。

#### A. 启动顺序（3 个终端）

终端 1（网页服务）：
```powershell
python tools/vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765
```

终端 2（串口桥接）：
```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --echo
```

终端 3（标准验收套件）：
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite standard_acceptance
```

浏览器打开：
`http://127.0.0.1:8765`

#### B. 页面验收点（按顺序）

1. 会话摘要可见套件结论  
判据：联调时间线摘要里出现“套件”芯片，显示 `suite_name + PASS/FAIL + 通过/失败计数`。

2. 失败项可跳转并高亮  
判据：测试结果历史里点击“跳转失败项”后，时间线自动切换到对应会话，并高亮对应 `suite_check`。

3. 选中检查详情完整  
判据：详情面板显示检查名、结果、命令、原因、备注、原始串口行。

4. 复制动作可用  
判据：  
`复制选中检查` 粘贴结果包含 `check/result/command/reason/line`。  
`复制本轮失败清单` 粘贴结果包含多条失败项明细。

5. 导出动作可用  
判据：下载并生成：
- `*_suite_failures.txt`
- `*_suite_full_report.txt`

6. 完整报告内容正确  
判据：`*_suite_full_report.txt` 同时包含：
- 总检查数
- 通过数
- 失败数
- 通过项列表
- 失败项详细上下文

#### C. 一轮通过标准

满足下面 3 条即判定本轮通过：

- 套件结论在会话摘要和时间线都可见
- 失败项定位链路（历史 -> 时间线 -> 详情）可用
- 复制/导出产物可直接交付协作方
### 7.14 测试结果历史新增 session_logs 兜底回填

这次联调里暴露了一个很真实的使用路径：
- 先停掉 `node_a_serial_bridge`，单独跑 `track_injector --suite standard_acceptance`
- `session_logs/*.jsonl` 会完整写出 `suite_started / suite_check / suite_finished`
- 但 `latest_test_results.json` 因为没有 bridge 参与，仍然可能是空的

结果就是页面上会出现一种割裂感：
- “联调时间线”能看到这轮 suite 结论
- “测试结果历史”却还是空白

这次补的就是这个缺口：
- `tools/vision_web_server_视觉网页服务.py` 的 `/api/test-results` 不再只原样返回 `latest_test_results.json`
- 它会先读正式历史文件
- 再扫描 `captures/session_logs/*.jsonl`
- 如果发现某轮会话只有 `suite_finished`、没有正式 `test_result` 历史记录，就自动回填一条“历史结果风格”的兜底记录

兜底记录会尽量保持和原历史结构一致，至少补齐：
- `scenario_name`
- `rid_mode`
- `result_label`
- `suite_name`
- `suite_passed`
- `suite_failed`
- `suite_report`
- `started_ms / finished_ms`

这样即使你先单独跑 suite，之后再开 bridge 或直接开网页：
- “联调时间线”仍然照常显示会话级结果
- “测试结果历史”也能补看到这轮 `standard_acceptance`
- 已有的 bridge 正式结果优先，不会被兜底记录覆盖

### 7.15 联调时间线顶部结果芯片改为优先显示 suite 结论

在 7.14 之后，页面里还剩一个小割裂点：
- 顶部“套件”芯片已经能显示 `PASS / FAIL`
- 但旁边“结果”芯片在没有正式 `test_result` 的会话里，仍可能显示 `NONE / NONE`

这次继续做了两层补齐：
- 服务端会话摘要里，如果 `result_label` 还是 `NONE`，但 `suite_finished` 已经有结论，就让 `result_label` 继承 `suite_result`
- 前端 `vision_dashboard.html` 的“结果”芯片在没有正式结果时，会直接显示：
  - `PASS` 或 `FAIL`
  - 并额外标注 `套件兜底`

这样你后面看页面时，不会再遇到：
- 左边明明写着套件 `PASS`
- 右边结果却还是 `NONE / NONE`

现在这块语义更统一了：
- 有正式 `test_result`：优先显示正式结果
- 没有正式 `test_result`：显示 suite 结论，并明确告诉你这是“套件兜底”
### 7.16 当前测试结果卡片补齐“结果来源 + 自动兜底”

这次继续收口了一个阅读体验问题：
- 时间线和测试结果历史已经能看到 `PASS/FAIL`
- 但“测试结果简报”卡片有时还会停在 `NONE`

本次改动后：
- `/api/test-result` 现在会优先读正式 `latest_test_result.json`
- 如果正式结果不可用或还是 `NONE`，会自动回退到“测试结果历史最新一条”
- 这条最新记录本身已经带 `session_logs` 兜底能力，所以卡片也能同步看到 suite 结论

同时前端卡片新增了“来源”字段，直接显示：
- `正式结果`
- `历史结果`
- `套件兜底`

这样后面你看页面时会更直观：
- 结果值是什么
- 这个结果是从哪条链路来的

### 7.17 历史结果来源可见 + 会话切换自动选中首条检查

继续把页面阅读门槛往下压了一步：

- 联调时间线会话切换后，如果该会话里有 `suite_check`，页面会自动选中第一条检查并填充详情面板  
  这样不会再默认看到一排 `NONE` 才知道要手工点。

- 测试结果历史每条记录的“结果”列新增来源标签，直接可见：  
  - `正式结果`  
  - `历史结果`  
  - `套件兜底`

- 对套件兜底记录，历史表和展开详情里涉及主链统计的字段会显示 `N/A（套件兜底）`，避免误读为真实 `0 / 0`：  
  - 事件/接力  
  - 最后事件  
  - 轨迹变化  
  - 事件变化  
  - 接力变化

这样你后面看历史记录时会更清楚：
- 结果从哪来
- 哪些值是正式主链统计
- 哪些只是兜底展示

### 7.18 测试结果简报新增“一句话结论”

继续针对“看不懂一堆字段”的问题做了阅读优化：

- 测试结果简报卡片新增 `一句话` 行，格式类似：  
  `standard_acceptance：PASS（套件 7/7，来源：套件兜底）`

- 这行会自动结合：
  - 场景名
  - 结果（PASS/WARN/FAIL）
  - 套件通过数/总数（有则显示）
  - 结果来源（正式结果 / 历史结果 / 套件兜底）

- 同时在“测试结果简报”卡片里，如果是套件兜底结果，原来容易误读的字段会显示为  
  `N/A（套件兜底）`，不再显示看起来像真实统计的 `0/0`。

这次的目标很直接：
- 不要求先懂所有字段
- 先看“一句话结论”就能知道这轮大体结果和来源

### 7.19 测试结果历史拆分“结果 / 来源”两列

为了让表格浏览更直接，这次把“测试结果历史”里的结果展示进一步拆开：

- 原来一列里同时塞 `PASS + 来源标签`
- 现在拆成两列：
  - `结果`
  - `来源`

这样你扫表时会更快：
- 第四列只看结果（PASS/WARN/FAIL）
- 第五列单独看来源（正式结果/历史结果/套件兜底）

同时这次把测试结果历史表格的列数和 `colspan` 全部同步对齐，避免空表、报错行、展开行在不同状态下出现错位。

### 7.20 历史结果新增“只看兜底”筛选和来源计数

继续围绕“结果可信度一眼可见”做了一步增强：

- 测试结果历史新增筛选按钮：`只看兜底`
- 汇总条新增两项计数：
  - `正式 N`
  - `兜底 N`

这样后续回看时你可以快速回答两个问题：
- 当前页面里有多少是正式结果、多少是套件兜底
- 只看兜底记录时，哪些轮次还需要后续补正式链路验证

### 7.21 可靠性图例与行级色标

为了让“来源可信度”不用读字也能快速识别，这次继续加了可视化层：

- 在测试结果历史汇总区新增“可靠性图例”：
  - 正式（绿点）
  - 历史（灰点）
  - 兜底（黄点）

- 在测试结果历史每一行的“来源”列前增加同色小点；
- 展开详情里的“结果来源”也使用同样的小点+标签；
- 行级增加轻量左侧色标（正式/历史/兜底），滚动扫表时更容易区分。

这样后续你在同一屏里可以同时靠：
- 文案（正式/历史/兜底）
- 颜色（绿/灰/黄）
快速判断每条结果的可靠性来源。

### 7.22 测试结果历史新增“总览结论提示”

继续往“少解释也能用”推进，这次在测试结果历史顶部增加了固定提示条：

- 无记录时：`总览：还没有结果记录。`
- 有兜底结果时：提示当前兜底条数，并给出建议动作  
  `先启动 bridge，再跑一轮标准套件补齐正式链路`
- 无兜底结果时：给出可回归结论  
  `当前结果已来自正式/历史链路，可直接用于回归结论`

这条提示直接复用现有汇总计数（正式/兜底），不新增新的数据来源，保证判据一致。

### 7.23 看板新增“术语速读”，直接解释套件 / bridge / 有无兜底

为了降低联调阅读门槛，这次在“测试结果历史”里新增了一个固定的“术语速读”区，不用再靠记忆理解术语。

新增内容：

- `套件（Suite）`：就是一组固定检查项（例如 `standard_acceptance` 的 7 项 PASS/FAIL）。
- `Bridge`：串口桥接进程（`node_a_serial_bridge`），负责把 Node A 串口输出写成看板 JSON。
- `有兜底`：来源显示“套件兜底”，表示这轮主要来自 `session_logs` 回填，不是 bridge 产出的正式 `test_result`。
- `无兜底`：来源来自“正式结果/历史结果”，可以直接用于回归结论。

同时增加了“当前判定”动态标签：

- 没有结果：显示“暂无判定”
- 有兜底：显示“有兜底 N 条”，并提示先启 bridge 再补跑一轮套件
- 无兜底：显示“无兜底（正式/历史）”，提示可直接用于回归结论

这部分仅是前端展示增强，不改串口协议、不改服务端数据结构，不影响现有验证流程。

### 7.24 联调时间线新增“逐项陪跑判定”关卡面板

为了让你不必逐行读终端输出，这次把 suite 检查项聚合成 4 个中文关卡，直接显示在“联调时间线”顶部。

关卡映射如下：

- `1 基线回归`：`idle_baseline`
- `2 事件开启`：`event_open_brief + event_open_risk + event_open_status`
- `3 风险回落闭环`：`risk_downgrade_event_status + risk_downgrade_last_event`
- `4 丢轨闭环`：`track_lost_last_event`

每个关卡都会显示：

- 状态：`PASS / FAIL / 进行中 / 待执行`
- 进度：已通过检查数 / 该关卡总检查数
- 失败项：当前关卡失败的检查名
- 待执行：当前关卡尚未出现的检查名

同时面板底部给出“下一步动作”：

- 有失败时：优先提示失败检查名及建议查看命令
- 无失败但未跑完时：提示下一项检查和对应命令（如 `BRIEF`、`EVENT,STATUS`、`LASTEVENT`）
- 全部通过时：提示可直接看回归结论

这一条仍是前端可视化增强，不改变后端数据源和验证口径。

### 7.25 逐项陪跑判定支持“点关卡定位 + 复制下一步命令”

在 7.24 的基础上，这次把“看懂”进一步做成“可操作”：

- 点击任一关卡卡片，会自动定位到对应的 `suite_check` 明细（如果该检查已出现）。
- 如果该检查还没出现，会直接提示该检查名和建议命令，不再让你自己猜下一步。
- 关卡面板底部新增“命令”标签和“复制下一步命令”按钮，可一键复制（例如 `BRIEF`、`EVENT,STATUS`、`LASTEVENT`）。

判定优先级保持一致：

- 有失败：优先指向失败检查
- 无失败但未跑完：指向下一项待执行检查
- 全部通过：显示无下一步命令（`NONE`）

这样你在页面里就能完成“看状态 -> 找检查 -> 拿命令”的闭环，不必来回切终端和文档。

### 7.26 新增“下一步操作清单”自动判定（Bridge / Suite）

继续把页面从“可读”推进到“可执行”：

- 在“逐项陪跑判定”下方新增“下一步操作清单”。
- 页面会自动结合 3 类信息做判定：
  - Bridge 是否在线（Node A 在线状态）
  - 关卡当前状态（失败 / 进行中 / 全通过）
  - 结果来源统计（正式 vs 兜底）

自动给出的动作逻辑：

- Bridge 离线：先启动 bridge
- Bridge 在线但未开始套件：先跑标准套件
- 有失败关卡：先看失败项并按下一步命令复测
- 全通过但有兜底：建议 bridge 在线再补跑一轮，补齐正式链路
- 全通过且无兜底：可直接作为回归结论

新增了可复制命令能力：

- 复制启动 Bridge 命令
- 复制标准套件命令
- 支持在页面里填写串口号（默认 `COM4`），命令实时同步

这条仍是前端层增强，不改后端协议和数据格式。

### 7.27（执行日期：2026-04-07，对齐 4.8 / 2026-04-08）补齐三项缺口

本轮按 4.8 计划把剩余缺口一次性补齐：

1. 纯模拟数据链（前端脱离硬件可推进）  
2. 场景定义表 V2（补视觉/网页预期）  
3. 日志对照模板 V1（联调复盘可直接套用）

#### 7.27.1 服务端新增 mock 数据模式

文件：
- `tools/vision_web_server_视觉网页服务.py`

新增能力：
- 所有核心 API 支持通过 `?mode=mock` 返回模拟数据（状态、事件、测试结果、时间线、抓拍等）
- 新增 `GET /api/data-source`，返回当前模式（`live/mock`）
- `GET /api/health` 也带模式字段，便于前端识别链路来源

这样网页端可在没有串口/硬件在线时，直接用模拟链路推进 UI 和交互开发。

#### 7.27.2 看板新增“真实/模拟链路”切换

文件：
- `tools/vision_dashboard.html`

新增能力：
- 顶部新增数据源模式切换（真实链路 / 模拟链路）
- 当前模式会持久化到本地（刷新后保留）
- 模拟模式下显示显式提示条，避免误把模拟数据当现场真实状态
- 所有数据请求自动携带模式参数，保证同一轮渲染口径一致

#### 7.27.3 新增文档产物（4.8 标准件）

新增文件：
- `docs/2026-04-08_scenario_definition_v2（场景定义表V2）.md`
- `docs/2026-04-08_log_reconciliation_template_v1（日志对照模板）.md`

场景定义表 V2：
- 每个场景补齐网页显示、抓拍触发、事件卡片、历史留痕、视觉 LOCKED 预期

日志模板 V1：
- 一轮联调从“输入命令 -> 三方对照 -> 不一致项 -> 最终结论”可直接填表复盘

### 7.28（执行日期：2026-04-07，提前对齐 4.9 / 2026-04-09）单节点联调闭环增强

本轮新增内容聚焦 4.9 的“主链 + 网页 + 接口联动”：

1. `bridge` 增加链路一致性判定字段  
   - 文件：`tools/node_a_serial_bridge_NodeA串口桥接.py`  
   - 新增字段：`consistency_status / consistency_expected_main_state / consistency_warnings`  
   - 用于快速发现“主链语义与网页映射是否错位”。

2. 网页增加一致性可视化卡片  
   - 文件：`tools/vision_dashboard.html`  
   - Node A 卡片新增“链路一致性”“映射告警”两行，直接显示 `OK/WARN` 和告警摘要。

3. 固件新增云台粗转向入口命令  
   - 文件：`src/main.cpp`  
   - 新命令：`COARSEAIM,x,y`  
   - 作用：基于雷达坐标快速给出云台粗转向角（作为视觉融合前置接口）。

4. 补齐 4.9 文档产物 V1  
   - `docs/2026-04-09_single_node_tuning_table_v1（单节点联调参数表V1）.md`  
   - `docs/2026-04-09_web_field_mapping_v1（网页字段映射表V1）.md`

### 7.29（执行日期：2026-04-08，持续推进 4.9）粗转向入口纳入套件与看板

本轮把“COARSEAIM 入口已接上”从代码能力升级到“可验收能力”：

1. `track_injector` 新增粗转向检查项  
   - 文件：`tools/track_injector_轨迹注入器.py`  
   - 套件：`single_node_realtime_v1`  
   - 新检查：`scenario1_coarse_aim_status`（验证 `STATUS` 里 `test_mode=1` 且 `servo_enabled=1`）。

2. 看板关卡改为按套件动态切换  
   - 文件：`tools/vision_dashboard.html`  
   - `standard_acceptance` 与 `single_node_realtime_v1` 使用不同关卡定义；  
   - “复制当前套件命令”会随会话自动切换，不再固定 `standard_acceptance`。

3. 套件执行指南同步更新  
   - 文件：`docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - 明确 `single_node_realtime_v1` 现为 7 项检查。

### 7.30（执行日期：2026-04-08，持续推进 4.9）粗转向失败提示可诊断化

这轮是低风险可用性增强，目标是“失败时可直接定位原因”，不再只给抽象失败字段。

1. `track_injector` 增加 `COARSEAIM` 兼容性提示  
   - 文件：`tools/track_injector_轨迹注入器.py`  
   - 变更：`single_node_realtime_v1` 在执行 `COARSEAIM` 后会捕获回包；若检测到 `Unknown command: COARSEAIM`，会在失败原因中追加明确提示：  
     - `COARSEAIM not supported by current firmware; flash latest firmware and rerun this suite.`  
   - 结果：当板子固件偏旧时，终端可直接给出“先刷固件再重测”的动作建议。

2. 套件指南补齐同口径故障排查  
   - 文件：`docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - 变更：新增 `scenario1_coarse_aim_status` 的失败排查说明，和脚本提示保持一致。

### 7.31（执行日期：2026-04-08，持续推进 4.9）新增 Node-Web 一致性自动核对脚本

这轮把“串口日志对、bridge 解析对、网页显示对”补成可直接执行的自动检查，不再依赖人工逐字段肉眼对比。

1. 新增一致性核对脚本  
   - 文件：`tools/node_web_consistency_check_NodeA网页一致性核对.py`  
   - 核对链路：`captures/latest_node_status.json` vs `/api/node-status`  
   - 默认附加检查：  
     - `/api/health` 可用  
     - `/api/data-source` 为 `live`（可用 `--allow-mock` 放宽）  
     - `stale_age_ms` 不超过阈值（默认 `5000ms`）  
   - 输出：逐字段 `PASS/FAIL` + 最终 `result=PASS/FAIL`。

2. 4.9 指南加入固定第 5 步  
   - 文件：`docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - 新增命令：  
     - `python tools/node_web_consistency_check_NodeA网页一致性核对.py --base-url http://127.0.0.1:8765`

3. 字段映射表加入“辅助核对命令”  
   - 文件：`docs/2026-04-09_web_field_mapping_v1（网页字段映射表V1）.md`  
   - 作用：把文档口径和可执行口径绑定，减少“看懂了但不会验”的断层。

### 7.32（执行日期：2026-04-08，持续推进 4.9）回收“独立计划看板”改动

按用户要求回收这轮偏离：不再新增独立计划看板文档，避免和现有 skill 流程重复。

1. 移除独立计划看板文件  
   - 已删除：`docs/2026-04-09_execution_plan_board_v1（执行计划看板V1）.md`

2. 交接规则改为“回复内计划”  
   - 文件：`docs/window_handoff_summary（窗口交接总结）.md`  
   - 规则口径：用户说“继续推进”时，先给本轮计划（DONE/DOING/TODO），但直接写在回复中，不新增独立文档。

### 7.33（执行日期：2026-04-08，持续推进 4.9）一致性核对升级为“连续观测模式”

这轮继续补 4.9 的“状态是否乱跳”判定，不再只做单点快照核对。

1. 一致性脚本新增 watch 模式  
   - 文件：`tools/node_web_consistency_check_NodeA网页一致性核对.py`  
   - 新参数：  
     - `--watch-seconds`：观测时长（`0` 表示单次核对）  
     - `--interval-s`：采样间隔  
     - `--max-fail-samples`：允许失败样本数  
     - `--quiet-pass`：仅输出失败项，减少终端噪声  
   - 新输出：  
     - `Node-Web Consistency Watch Report`  
     - `samples/pass_samples/fail_samples` 统计  
     - 最终 `result=PASS/FAIL`。

2. 4.9 执行指南补入稳定性观测步骤  
   - 文件：`docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - 新增第 6 步：15 秒观测命令（默认要求全样本通过）。

3. 字段映射文档补入稳定性观测命令  
   - 文件：`docs/2026-04-09_web_field_mapping_v1（网页字段映射表V1）.md`  
   - 作用：把“字段一致”与“稳定一致”两层口径都固定下来。

### 7.34（执行日期：2026-04-08，持续推进 4.9）修复 watch 模式“服务离线噪声刷屏”

根据实测反馈，若网页服务不可达，旧版会把所有字段都报成 mismatch，导致误判和大量噪声。

本轮修复：

1. API 不可达时跳过字段比对  
   - 文件：`tools/node_web_consistency_check_NodeA网页一致性核对.py`  
   - 行为：若 `/api/health` 或 `/api/node-status` 请求失败，直接标记为链路不可达，跳过 `checked_fields` 比对（避免级联误报）。

2. watch 模式首样本失败可提前终止  
   - 默认行为：首样本即 API 不可达时，输出 `watch_abort=API_UNREACHABLE_ON_FIRST_SAMPLE` 并结束观测。  
   - 可选参数：`--no-abort-on-api-fail`（需要持续观测离线状态时使用）。

3. 失败输出改为汇总  
   - 末尾改成 `failure_summary`（按原因聚合计数），不再逐样本展开海量重复行。

### 7.35（执行日期：2026-04-08，持续推进 4.9）新增真实雷达两场景留档脚本

这轮补齐 4.9 剩余项里的“实机两场景可留档”，避免只靠口头结论。

1. 新增实机场景核对脚本  
   - 文件：`tools/real_radar_scenario_checker_实机场景核对.py`  
   - 场景：  
     - `sustained_target`（目标持续存在）  
     - `track_lost`（先有目标，再移走目标）  
   - 输出：终端 `PASS/FAIL` + `captures/real_radar_checks/*.json` 结构化报告。

2. 4.9 执行指南加入固定步骤  
   - 文件：`docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - 新增第 7 步：两场景留档命令。

3. 单节点参数表补入留档命令  
   - 文件：`docs/2026-04-09_single_node_tuning_table_v1（单节点联调参数表V1）.md`  
   - 作用：把联调参数与实机留档动作绑定到同一口径。

### 7.36（执行日期：2026-04-08，持续推进 4.9）新增实机报告汇总脚本

这轮补“收尾结论自动化”：把两场景单独 JSON 报告，汇总成一条可交付结论。

1. 新增汇总脚本  
   - 文件：`tools/real_radar_report_summary_实机报告汇总.py`  
   - 输入：`captures/real_radar_checks/*.json`  
   - 输出：`captures/latest_real_radar_summary.json`  
   - 判定：默认要求 `sustained_target` 与 `track_lost` 两场景都存在、都 PASS、且报告未过期（默认 24h）。

2. 4.9 指南新增“第 8 步汇总结论”  
   - 文件：`docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - 命令：`python tools/real_radar_report_summary_实机报告汇总.py --max-age-hours 24`

3. 单节点参数表同步  
   - 文件：`docs/2026-04-09_single_node_tuning_table_v1（单节点联调参数表V1）.md`  
   - 增加汇总命令，形成“采样留档 -> 汇总结论”闭环。

### 7.37（执行日期：2026-04-08，持续推进 4.9）`track_lost` 改为“两阶段引导 + 两阶段判定”

为了降低现场误操作，本轮把 `track_lost` 场景从“单窗口自由操作”改成“前半保持、后半移走”的明确节奏。

1. 脚本能力增强  
   - 文件：`tools/real_radar_scenario_checker_实机场景核对.py`  
   - 新增参数：  
     - `--track-lost-phase1-ratio`（默认 `0.5`）  
     - `--min-phase1-active-hits`（默认 `2`）  
     - `--min-lost-hits`（继续沿用）  
   - 新增输出：采样行带 `phase1_keep_target / phase2_remove_target` 标签，报告含 `scenario_metrics`。

2. 判定逻辑增强  
   - phase1：必须观测到足够的 active/confirmed 命中；  
   - phase2：必须观测到 LOST 命中，且末样本不能还保持 `track_active=1`。

3. 指南和参数表同步  
   - `docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - `docs/2026-04-09_single_node_tuning_table_v1（单节点联调参数表V1）.md`

### 7.38（执行日期：2026-04-08，持续推进 4.9）实机场景脚本补 `warmup` 与阶段切换提示

为减少现场“动作已做但采样没跟上”的误判，本轮增强实机场景脚本的人机交互提示。

1. 脚本新增预热参数  
   - 文件：`tools/real_radar_scenario_checker_实机场景核对.py`  
   - 新参数：`--warmup-s`（默认 `2s`）  
   - 行为：采样前倒计时预热，预热结束后再开始记录样本。

2. `track_lost` 新增阶段切换提醒  
   - 在进入 `phase2_remove_target` 前打印明确提示，避免现场忘记切换动作。

3. 报告增加阶段窗口元数据  
   - 新字段：`phase_windows`（记录 phase1/phase2 的采样索引范围）  
   - 作用：复盘时能明确知道每条样本对应哪个动作阶段。

4. 指南和参数表命令同步  
   - `docs/2026-04-09_suite_execution_guide_v1（套件执行指南V1）.md`  
   - `docs/2026-04-09_single_node_tuning_table_v1（单节点联调参数表V1）.md`

### 7.39（执行日期：2026-04-08，按 4.10 计划预置）风险链 + 事件链 + 视觉触发链联合套件

本轮按 4.10（周五）计划预置“联合强测”入口，重点不再只看风险分级，而是把风险、事件、视觉触发三条链一起判定。

1. 新增 4.10 联合套件  
   - 文件：`tools/track_injector_轨迹注入器.py`  
   - 新套件：`risk_event_vision_chain_v1`  
   - 覆盖 6 个检查场景：  
     - 短时无 RID 不直接事件化  
     - 持续无身份风险升级  
     - 合法目标低风险不抓拍  
     - 身份异常快速升风险  
     - 高风险触发视觉锁定/抓拍预备  
     - 丢轨后平稳回落并关闭事件

2. 统一为单文件文档交付（减少 md 文件数量）  
   - 文件：`docs/2026-04-10_joint_chain_bundle_v1（联合链路交付包V1）.md`  
   - 单文件内收拢：  
     - 风险升级触发矩阵 V1  
     - 状态报文格式 V1  
     - 事件报文格式 V1  
     - 联合链路测试记录模板 V1

3. 保持计划内边界  
   - 本轮不改主链状态机、不改固件风险算法；  
   - 只新增 4.10 执行入口与交付文档，便于你直接实操和留档。

### 7.40（执行日期：2026-04-08，按 4.10 计划修正）短时无 RID 事件门槛与场景1判定对齐

根据 `risk_event_vision_chain_v1` 实测（5/6，场景1失败），本轮按 A 方案修正“短时无 RID 不直接事件化”。

1. 固件新增短时门槛  
   - 文件：`include/AppConfig.h`  
   - 新参数：`EventConfig::MissingRidEventMinDurationMs = 800`  
   - 语义：无 RID 目标短时进入时，先做风险观察，不立即开事件。

2. 事件开启判定接入门槛  
   - 文件：`src/main.cpp`  
   - `isEventEligible(...)` 改为带 `now` 入参，并在 `RID_MISSING` 时判断轨迹存活时长。  
   - 若轨迹存活时长 `< 800ms`，即使风险已升，也暂不 `EVENT_OPENED`。

3. 4.10 套件场景1判定收敛到“是否直接事件化”  
   - 文件：`tools/track_injector_轨迹注入器.py`  
   - `scenario1_short_missing_rid_no_direct_event` 不再强制 `confirmed=0`，只强制 `event_active=0`（更贴合 4.10 原始口径）。

4. 单文件交付包同步参数口径  
   - 文件：`docs/2026-04-10_joint_chain_bundle_v1（联合链路交付包V1）.md`  
   - 增补 `MissingRidEventMinDurationMs=800` 说明，便于答辩和复盘统一口径。

### 7.41（执行日期：2026-04-08，按 4.10 计划验收）联合套件实测 6/6 PASS

本轮完成固件烧录后，按 4.10 联合链路口径实测：

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -t upload
python tools/track_injector_轨迹注入器.py --port COM4 --suite risk_event_vision_chain_v1 --validate-rid MISSING
```

实测结论：

1. 套件总结果  
   - `suite=risk_event_vision_chain_v1 total=6 passed=6 failed=0`

2. 关键通过项  
   - `scenario1_short_missing_rid_no_direct_event`：PASS（短时无 RID 不直接事件化）  
   - `scenario5_high_risk_visual_capture_ready`：PASS（高风险触发视觉锁定/抓拍预备）  
   - `scenario6_track_lost_smooth_recover`：PASS（丢轨后平稳回落并关闭事件）

3. 4.10 主线结论  
   - “发现 -> 研判 -> 告警 -> 视觉锁定/抓拍预备 -> 成事件 -> 丢失回落”链路已形成可重复证据。

### 7.42（执行日期：2026-04-08，按 4.10 计划收口）新增状态/事件报文契约自动核对

为把“报文格式定稿”从人工目测升级为自动验收，本轮新增契约核对脚本。

1. 新增报文契约核对工具  
   - 文件：`tools/uplink_packet_contract_check_报文契约核对.py`  
   - 默认输入：  
     - `captures/latest_node_status.json`（状态报文归一化结果）  
     - `captures/latest_node_events.json`（事件报文归一化结果）  
   - 默认输出：`captures/latest_uplink_contract_report.json`  
   - 结果：`result=PASS/FAIL` + 缺失字段清单。

2. 4.10 单文件交付包同步执行命令与验收口径  
   - 文件：`docs/2026-04-10_joint_chain_bundle_v1（联合链路交付包V1）.md`  
   - 新增“终端4 契约核对命令”与“通过标准（status/event failures 均为 0）”。

### 7.43（执行日期：2026-04-09，持续推进 4.10）交付判定补“时序防误判”

这轮继续做低风险增量，不改固件主链，只补“旧报告误判为本轮通过”的边界。

1. 套件快照新增契约新鲜度判定  
   - 文件：`tools/track_injector_轨迹注入器.py`  
   - 规则：生成 `latest_acceptance_snapshot.json` 时，若 `latest_uplink_contract_report.json.checked_ms` 早于本轮 `suite_finished_ms`，则判为旧契约结果。  
   - 输出新增字段：  
     - `suite_finished_ms`  
     - `contract_fresh`  
     - `contract_stale_by_ms`  
   - 判定收敛：`contract_ok = (contract_result == PASS) and contract_fresh`。

2. 总闸门脚本新增时间顺序一致性核对  
   - 文件：`tools/delivery_bundle_readiness_check_交付包就绪核对.py`  
   - 新增口径：  
     - 契约核对时间不得早于 suite 完成时间；  
     - 快照更新时间不得早于契约核对时间；  
     - 证据生成时间若早于 session 启动过多，判为时序异常。  
   - 新参数：`--max-backward-ms`（默认 `1500`，用于容忍小幅时间抖动）。

3. 本次收益  
   - 现场执行仍是原来三步（suite -> contract -> readiness），但能自动识别“漏跑 contract、沿用旧 PASS”的误操作。  
   - 对 4.10 交付口径更稳，避免“看起来全绿、其实时间错序”的假通过。

### 7.44（执行日期：2026-04-09，按 4.11 计划预置）事件证据闭环最小落地

这轮按你给的 4.11 方向，先把“事件对象 + 抓拍证据 + 网页展示”做成可演示的最小闭环。

1. Node A 串口桥接新增事件持久化仓  
   - 文件：`tools/node_a_serial_bridge_NodeA串口桥接.py`  
   - 新增输出：`captures/latest_node_event_store.json`（默认）。  
   - 新参数：  
     - `--event-store-file`  
     - `--event-store-limit`  
   - 行为：  
     - 除原有 `latest_node_events.json`（短历史）外，新增“持久事件仓”；  
     - 事件记录补齐详情字段（`risk_level / rid_status / x_mm / y_mm / reason / event_close_reason` 等），便于网页详情展示与后续证据回放。

2. vision_bridge 抓拍日志改为追加 + 自动绑定事件号  
   - 文件：`tools/vision_bridge_视觉桥接.py`  
   - 变更：  
     - `capture_records.csv` 写入从覆盖改为追加（跨轮次留痕）；  
     - 新增 `--node-status-file`（默认 `captures/latest_node_status.json`）；  
     - 若未显式传 `--event-id`，抓拍会自动读取当前节点状态中的事件号并写入抓拍记录。  
   - 收益：抓拍与事件对象可自动挂接，不再只靠手工传 event_id。

3. 网页服务新增“事件仓 / 事件详情”接口  
   - 文件：`tools/vision_web_server_视觉网页服务.py`  
   - 新接口：  
     - `/api/node-event-store`（最近事件仓记录）  
     - `/api/node-event-detail?event_id=...`（单事件详情 + 对应抓拍）  
   - 新参数：`--node-event-store-file`（默认 `captures/latest_node_event_store.json`）。

4. 看板新增“事件详情（最小回放）”卡片  
   - 文件：`tools/vision_dashboard.html`  
   - 行为：  
     - 点选“Node A 最近事件”某一行后，自动展示该事件详情；  
     - 详情字段包含：`事件编号 / 触发时间 / 风险等级 / 节点编号 / 坐标 / RID 状态 / 触发原因 / 抓拍路径`；  
     - 若有对应抓拍图，直接展示图片证据；无图时显示占位提示。

5. 本轮执行口径（4.11 最小闭环）  
   - 主链实时状态仍由 `/api/node-status` 提供；  
   - 事件留痕由 `latest_node_event_store.json` 提供；  
   - 抓拍证据由 `capture_records.csv + captures/*.jpg` 提供；  
   - 网页点击事件即可查看“事件对象 + 抓拍证据”。

### 7.45（执行日期：2026-04-09，按 4.11 计划修正）空事件表修复：桥接主动轮询事件语义

针对实测“Node A 最近事件表为空（count=0）”的问题，本轮补一个低风险修正：

1. 桥接新增事件语义轮询  
   - 文件：`tools/node_a_serial_bridge_NodeA串口桥接.py`  
   - 新参数：  
     - `--event-status-interval`（默认 `2.0s`）  
     - `--last-event-interval`（默认 `3.0s`）  
   - 行为：桥接在常规 `STATUS/SELFTEST` 轮询之外，主动发送 `EVENT,STATUS` 与 `LASTEVENT`，把结果写入事件历史与事件仓。

2. 事件提取逻辑补 `EVENT,STATUS` 并增强字段回退  
   - `EVENT_HISTORY_PREFIXES` 新增 `EVENT,STATUS`；  
   - `event_id/reason` 支持从 `current_event_id/last_event_id/last_reason` 回退提取；  
   - 对“无事件编号的 EVENT,STATUS”做过滤（不入库），避免空状态刷屏。

3. 修复结果  
   - 页面“Node A 最近事件”不再长期空表；  
   - 事件详情卡片可在真实链路下更稳定地拿到事件对象（即使 `UPLINK,EVENT` 行不频繁出现）。

### 7.46（执行日期：2026-04-09，按 4.11 计划修正）bridge 重启不再清空事件历史

针对“刚跑完套件有事件，重启 bridge 后又变成 0 条”的问题，本轮补充：

1. bridge 启动时保留已有 `latest_node_events.json`  
   - 文件：`tools/node_a_serial_bridge_NodeA串口桥接.py`  
   - 旧行为：启动即写空 `event_history`。  
   - 新行为：启动先加载已有事件历史，再继续增量写入。

2. bridge 启动时自动把历史事件并入事件仓  
   - 启动阶段会将 `latest_node_events.json` 里的记录回填到 `latest_node_event_store.json`。  
   - 作用：避免“事件列表有数据，但事件详情仓为空”的断层。

3. 结果  
   - 跑完 `track_injector` 后，即使重启 bridge，事件列表与事件详情来源都不会被清零。  
   - 网页“Node A 最近事件”与“事件详情（最小回放）”可连续使用。
