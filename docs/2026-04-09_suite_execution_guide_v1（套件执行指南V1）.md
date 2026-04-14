# 2026-04-09 套件执行指南 V1

## 目标
给 4.9 联调一个“拿来就跑”的执行口径，避免手工拼命令。

## 套件列表

- `standard_acceptance`
作用：完整 7 项验收，偏回归完整性。
- `single_node_realtime_v1`
作用：4.9 两场景最小闭环，偏“主链 + 网页实时显示”联调。

## 推荐执行顺序（4.9）

1. 启动网页服务
```powershell
python tools/vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765
```

2. 启动串口 bridge
```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --echo
```

3. 跑 4.9 两场景套件
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite single_node_realtime_v1 --validate-rid MISSING
```

4. 如需做完整回归，再跑
```powershell
python tools/track_injector_轨迹注入器.py --port COM4 --suite standard_acceptance --validate-rid MISSING
```

5. 跑“bridge ↔ 网页”一致性自动核对（4.9 新增）
```powershell
python tools/node_web_consistency_check_NodeA网页一致性核对.py --base-url http://127.0.0.1:8765
```

6. 做 15 秒稳定性观测（判断是否“短时闪错位”）
```powershell
python tools/node_web_consistency_check_NodeA网页一致性核对.py --base-url http://127.0.0.1:8765 --watch-seconds 15 --interval-s 1 --max-fail-samples 0 --quiet-pass
```

7. 跑真实雷达两场景留档（4.9 收尾）
```powershell
python tools/real_radar_scenario_checker_实机场景核对.py --scenario sustained_target --duration-s 20 --warmup-s 2
python tools/real_radar_scenario_checker_实机场景核对.py --scenario track_lost --duration-s 20 --warmup-s 2 --track-lost-phase1-ratio 0.5 --min-phase1-active-hits 2 --min-lost-hits 2
```

8. 汇总两场景结果（生成单条 PASS/FAIL 结论）
```powershell
python tools/real_radar_report_summary_实机报告汇总.py --max-age-hours 24
```

## `single_node_realtime_v1` 检查项

1. `scenario1_idle_baseline`
2. `scenario1_tracking_open_brief`
3. `scenario1_tracking_open_event`
4. `scenario1_tracking_open_risk`
5. `scenario1_coarse_aim_status`
6. `scenario2_risk_recover_event_closed`
7. `scenario2_track_lost_last_event`

## 网页端联调关注点

- Node A 卡片中的“链路一致性”应尽量保持 `OK`。
- “映射告警”若出现，优先看字段是否短时过渡还是稳定错位。
- 联调时间线中应看到 `suite_started -> suite_check -> suite_finished`。

## 备注

- 看板“下一步操作清单”的套件命令会自动跟随当前会话切换（`standard_acceptance` 或 `single_node_realtime_v1`）。
- 若 `scenario1_coarse_aim_status` 失败且提示 `COARSEAIM not supported`，说明板子固件版本偏旧；先重新烧录最新固件，再重跑 `single_node_realtime_v1`。
- 一致性核对脚本默认要求 `mode=live`；若你在看板里切到模拟链路，请加 `--allow-mock` 再执行。
- `--watch-seconds` 用于连续观测，建议联调收尾固定跑一次（10~20 秒）。
- 若首样本出现 `health_api/web_node_status request_failed`，脚本会提前终止 watch（默认行为），直接提示是“网页服务不可达”而非字段错位。
- 真实雷达场景核对脚本会在 `captures/real_radar_checks/` 自动写入 JSON 报告，供周四留档复盘。
- `track_lost` 现在按“两阶段”执行：前半程保持目标、后半程移走目标；终端会打印 phase 指引。
- 实机场景脚本支持 `--warmup-s` 预热，建议保持 `2s`，避免刚切操作窗口就开始采样导致假失败。
- 报告汇总脚本会输出 `captures/latest_real_radar_summary.json`，可作为“4.9 实机两场景是否完成”的单点结论。
