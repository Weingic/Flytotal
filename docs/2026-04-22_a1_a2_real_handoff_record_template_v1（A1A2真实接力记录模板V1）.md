# 2026-04-22 A1A2 真实接力记录模板 V1

## 基本信息
- 测试日期：
- 测试地点：
- 记录人：
- 场景编号：
- 目标说明：

## 节点与环境
- A1 设备：
- A2 设备：
- 中心机：
- dashboard 地址：
- 视频录制文件名：

## 真实接力流程记录
### Step 1：目标进入 A1 区域
- 时间：
- 观测现象：
- 证据：
  - dashboard 截图：
  - 串口/bridge 日志：

### Step 2：A1 触发跟踪 / 风险
- 时间：
- 观测现象：
- 关键字段：
  - `event_id`：
  - `node_id`：
  - `risk_level`：
  - `rid_status`：
- 证据：
  - 事件详情截图：
  - 日志片段：

### Step 3：A1 发出 handoff
- 时间：
- 观测现象：
- 关键字段：
  - `prev_node_id`：
  - `handoff_from`：
  - `handoff_to`：
  - `continuity_hint`：
- 证据：
  - dashboard 截图：
  - 事件对象 / 导出截图：
  - 日志片段：

### Step 4：A2 接续显示目标与事件来源
- 时间：
- 观测现象：
- 关键字段：
  - `node_id`：
  - `source_node`：
  - `prev_node_id`：
  - `handoff_from`：
  - `handoff_to`：
  - `continuity_hint`：
- 证据：
  - dashboard 截图：
  - 事件详情截图：
  - 导出 JSON 文件名：

## 结果判定
- 是否能明确讲清起始节点：是 / 否
- 是否能明确讲清当前节点：是 / 否
- handoff 是否只存在于代码里：是 / 否
- 页面 / 日志 / 导出是否三处一致：是 / 否

## 问题记录
- 现象：
- 可能原因：
- 是否阻塞答辩：

## 最终结论
- 本轮结果：PASS / PARTIAL / FAIL
- 答辩是否可讲：可直接讲 / 可保守讲 / 暂不讲
