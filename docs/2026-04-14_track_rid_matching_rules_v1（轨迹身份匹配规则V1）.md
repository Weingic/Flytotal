# 2026-04-14 轨迹-身份匹配规则 V1

## 1. 规则目标
解决“收到一次身份就永久合法”的风险，强制使用时间窗口和超时机制。

## 2. 核心参数
1. `RidConfig::MatchWindowMs = 1200`
2. `RidConfig::ReceiveTimeoutMs = 3000`
3. `EventConfig::MissingRidEventMinDurationMs = 800`

## 3. 匹配判定

### 3.1 合法匹配（进入 `RID_MATCHED`）
同时满足：
1. 轨迹存在（`track_active=1`）
2. 身份包有效期内（未超时）
3. 身份鉴权通过（`auth_status` 有效）
4. 白名单命中（`whitelist_tag` 命中）
5. 当前时间与身份接收时间差在 `MatchWindowMs` 内

### 3.2 仅接收未匹配（`RID_RECEIVED`）
满足：
1. 身份包已收到且未超时
2. 鉴权 + 白名单通过
3. 但当前不在轨迹匹配窗口内

### 3.3 失配/异常
1. 无身份：`RID_NONE`
2. 身份超时：`RID_EXPIRED`
3. 鉴权失败或白名单不通过：`RID_INVALID`

## 4. 风险与事件联动
1. `RID_NONE / RID_EXPIRED`：风险增加，但受 `MissingRidEventMinDurationMs` 保护，不立刻事件化。
2. `RID_INVALID`：风险显著增加，可更快进入可疑/高风险。
3. `RID_MATCHED`：风险降低，允许进入低风险链。

## 5. 规则解释（一句话版）
只有“轨迹存在 + 时间窗内 + 认证通过 + 白名单命中”的身份，才算合法匹配。
