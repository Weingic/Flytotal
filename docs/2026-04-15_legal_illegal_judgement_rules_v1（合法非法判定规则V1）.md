# 2026-04-15 合法/非法判定规则 V1

## 1. 判定目标
确保系统行为满足：
- 合法目标：不进入高危告警链。
- 非法/异常目标：不能被误放行。

## 2. 白名单状态定义
1. `WL_UNKNOWN`：无白名单记录或无法判定。
2. `WL_ALLOWED`：白名单允许。
3. `WL_DENIED`：白名单明确拒绝。
4. `WL_EXPIRED`：白名单记录已过期。

## 3. 主判定规则（V1）
### 3.1 合法目标链
满足以下条件时进入合法链：
1. 有活动轨迹（`track_active=1`）。
2. RID 包有效（鉴权通过）。
3. 白名单判定为 `WL_ALLOWED`。
4. 处于匹配时间窗内（`MatchWindowMs`）。

结果：
- `rid_status` 进入 `MATCHED`（或窗口外为 `RECEIVED`）。
- `hunter_state` 允许进入 `RID_MATCHED/TRACKING` 低风险链。
- 不应进入 `HIGH_RISK/EVENT`。

### 3.2 非法/异常目标链
1. `WL_DENIED` 或 RID 鉴权失败 -> `rid_status=INVALID`。
2. `WL_EXPIRED` -> `rid_status=EXPIRED`（不按合法放行）。
3. `WL_UNKNOWN` 且无有效身份 -> 维持可疑路径（不可直接放行）。

## 4. 网页与日志表达要求
1. 绿色：合法目标（`WL_ALLOWED` + 合法链）。
2. 黄色：可疑/待确认（`WL_UNKNOWN/WL_EXPIRED`、无身份等）。
3. 橙红：高风险/事件（`risk_level=HIGH_RISK/EVENT`）。

## 5. 4 个标准场景（验收口径）
1. 合法目标进入并持续存在。
2. 无身份目标进入。
3. 有身份但不在白名单。
4. 合法目标短时身份丢失后恢复。
