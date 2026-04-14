# 2026-04-14 RID 状态定义 V1

## 1. 固定状态枚举
本版本固定 `rid_status` 为以下 5 个：

1. `RID_NONE`
2. `RID_RECEIVED`
3. `RID_MATCHED`
4. `RID_EXPIRED`
5. `RID_INVALID`

## 2. 状态语义

| 状态 | 语义 | 典型风险方向 |
|---|---|---|
| `RID_NONE` | 当前未收到可用身份 | 进入可疑链（需配合轨迹） |
| `RID_RECEIVED` | 收到身份包，但未满足合法匹配条件 | 观察态，等待匹配或进一步判定 |
| `RID_MATCHED` | 在匹配窗口内，且白名单与鉴权通过 | 低风险链，允许进入 `HUNTER_RID_MATCHED` |
| `RID_EXPIRED` | 之前有身份，但超时未更新 | 回到可疑链（含缓冲） |
| `RID_INVALID` | 收到身份但鉴权失败或白名单不通过 | 保持可疑或升风险 |

## 3. 状态转移关键条件

| 触发条件 | 结果 |
|---|---|
| 未收到身份包 | `RID_NONE` |
| 收到身份包，鉴权+白名单通过，但不在匹配窗 | `RID_RECEIVED` |
| 收到身份包，鉴权+白名单通过，且在匹配窗内 | `RID_MATCHED` |
| 身份包超过 `ReceiveTimeoutMs` 未更新 | `RID_EXPIRED` |
| 鉴权失败或白名单不通过 | `RID_INVALID` |

## 4. 与 Hunter 状态机关系
1. 有轨迹 + 无身份（`RID_NONE` / `RID_EXPIRED`）-> 可疑链优先。
2. 有轨迹 + 身份匹配（`RID_MATCHED`）-> `HUNTER_RID_MATCHED` / 低风险链。
3. 有轨迹 + 异常身份（`RID_INVALID`）-> 可疑或高风险链。
4. 身份超时后不直接跳事件，仍走风险保持窗口。
