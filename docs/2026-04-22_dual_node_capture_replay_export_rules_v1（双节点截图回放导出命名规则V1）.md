# 2026-04-22 双节点截图回放导出命名规则 V1

## 目标
- 固定 5.1 现场的截图位、回放位和导出命名规则，避免测试完后资料对不上。

## 页面截图位
### 必拍 1：双节点总览
- 内容：
  - A1 / A2 卡片同时可见
  - 在线状态
  - `node_id / source_node`
  - `continuity_hint`
- 命名：
  - `dual_dashboard_overview_<date>_<scenario>.png`

### 必拍 2：接力发生时的双节点卡片
- 内容：
  - A1 -> A2 的 handoff 字段
  - `prev_node_id`
  - `handoff_from`
  - `handoff_to`
- 命名：
  - `dual_dashboard_handoff_<date>_<scenario>.png`

### 必拍 3：事件详情
- 内容：
  - `event_id`
  - `node_id`
  - `risk_level`
  - `rid_status`
  - 抓拍图或抓拍路径
- 命名：
  - `dual_event_detail_<date>_<event_id>.png`

## 回放截图位
### 必拍 4：导出列表
- 内容：
  - 刚导出的证据 JSON 出现在列表里
- 命名：
  - `dual_export_list_<date>_<event_id>.png`

### 必拍 5：导出回放
- 内容：
  - 打开导出记录后的回放界面
- 命名：
  - `dual_export_replay_<date>_<event_id>.png`

## 导出文件命名规则
- 真实接力样例：
  - `dual_handoff_<date>_<event_id>.json`
- 合法目标样例：
  - `ab_legal_<date>_<event_id>.json`
- 非合作目标样例：
  - `ab_illegal_<date>_<event_id>.json`

## 日志抓取规则
- bridge 日志：
  - `bridge_a1_<date>_<scenario>.log`
  - `bridge_a2_<date>_<scenario>.log`
- center 日志：
  - `center_<date>_<scenario>.log`

## 现场整理顺序
1. 先保存 dashboard 总览截图。
2. 再保存 handoff 时刻截图。
3. 再保存事件详情截图。
4. 导出 JSON 后保存导出列表截图。
5. 最后保存导出回放截图。

## 说明
- 如果某次真实场景失败，也按同样命名保留失败样例。
- 不允许现场结束后再用“final”“new”“最新版”这种名字重命名文件。
