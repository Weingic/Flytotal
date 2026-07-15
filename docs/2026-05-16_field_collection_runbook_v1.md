# 2026-05-16 Field Collection Runbook V1

## 2026-07-13 当前状态

本文件保留原计划入口，但旧版命令与距离表已经失效。当前唯一现场采集口径是：

[`docs/2026-06-08_real_data_collection_sop_v1.md`](2026-06-08_real_data_collection_sop_v1.md)

不要再使用旧版的 `captures/e2e_node_status.json`、固定 `source 1`、强制 `CSRT`，也不要把 30/50/80/100 米写成 LD2450 二维轨迹采集点。

## 现场快速清单

1. COM4 只能由一份 `node_a_serial_bridge` 占用，其他命令通过统一收件箱提交。
2. 当前 NodeA 状态源是 `captures/latest_node_status.json`。
3. 先通过统一收件箱发送 `REALINPUT,ON`、`TESTMODE,OFF` 和 `FUSION,ENABLE,1`，再运行 `python tools\field_collection_preflight.py --mode same-event`；只有物理摄像头、正式 V4b、增强融合和云测试全部达到 `GO 18/18` 才开始，并保留该报告作为 8 小时时间窗起点。
4. LD2450 轨迹只有在 `online=1`、`track_active=1`、`track_confirmed=1` 且位置/速度连续变化时才可写入 `real_tracks.csv`。
5. 每一段采集必须使用新的 `session-id`。重复编号会被采集器拒绝，避免两段时间轴被分类器合并。
6. LD2450 近距轨迹、V4b 视觉距离、LD2451 远距预警分别保存原始证据，不能相互代替。
7. 10/30/50 米属于视觉和远距预警的实测点；是否通过由当天真实记录决定，不预先写成系统能力。
8. 每段必须记录真实标签、实测距离、动作、天气、光照、遮挡、成功/失败和参考视频文件。
9. 不删除失败样本，不降低阈值换取好看的结果，不把离线视频或模拟轨迹包装成外场真机数据。
10. 核心矩阵为无人机、人物、车辆在 10/30/50 米各 3 次，共 27 次；另做静态杂波和正常人车环境各 20 分钟。
11. 每完成一组运行 `python tools\field_evidence_gate.py`；`GO 22/22`、距离剩余 0、长稳剩余 0 只表示矩阵齐全。
12. 全新真实事件严格报告固定保存为 `captures/latest_real_drone_strict_closure_report.json`；至少一条无人机报告必须记录到与该严格事件同号的实机融合样本；最终运行 `python tools\field_evidence_gate.py --mode mission-final`，只有 `GO 26/26` 才是整次任务收工条件。

## 最低有效结果

现场数据只有同时具备以下内容才可进入国赛材料：

```text
唯一 session-id
原始 CSV 或视频
对应状态/事件记录
真实目标与距离记录
成功、失败和误报统计
可复核的截图或导出文件
```

PC 完整回归 `25/25` 只证明工具逻辑；外场 `same-event 18/18` 预检、同一真实事件严格 `15/15`、矩阵 `22/22`、同采样实机融合和最终同场总门 `26/26` 必须分别取得。
