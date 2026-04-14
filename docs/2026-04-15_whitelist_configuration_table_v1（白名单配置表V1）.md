# 2026-04-15 白名单配置表 V1

## 1. 目标
在不引入数据库的前提下，先用本地配置表跑通“合法目标放行、非法目标不放行”的主链逻辑。

## 2. 字段定义
1. `rid_id`：身份唯一标识。
2. `owner`：所属单位/人员。
3. `label`：显示标签（用于网页和日志快速识别）。
4. `allowed`：是否允许（`true/false`）。
5. `expire_time_ms`：过期时间（毫秒；`0` 表示不过期）。
6. `note`：备注。

## 3. 当前固件内置白名单样例（src/main.cpp）
| rid_id | owner | label | allowed | expire_time_ms | note |
|---|---|---|---|---:|---|
| `SIM-RID` | `TeamA` | `LegalDemo` | `true` | `0` | 默认合法演示目标 |
| `SIM-RID-001` | `LabA` | `UAV-001` | `true` | `0` | RID,MSG 合法样例 |
| `SIM-RID-999` | `LabA` | `UAV-999` | `false` | `0` | 非白名单样例 |
| `SIM-RID-EXPIRED` | `LabA` | `UAV-EXP` | `true` | `1000` | 过期样例 |

## 4. 当前输出字段
串口与桥接状态已输出：
- `wl_status`
- `wl_owner`
- `wl_label`
- `wl_expire_time_ms`
- `wl_note`
- `rid_whitelist_hit`

## 5. 联调命令
1. `WL,LIST`：查看白名单表。
2. `WL,STATUS`：查看当前目标的白名单判定结果。
3. `RID,STATUS`：联动查看 RID 与白名单状态。
