# 2026-04-15 身份超时与回落规则 V1

## 1. 目标
避免“合法目标身份短抖动就被立刻打成可疑/高危”的误报。

## 2. 关键参数（当前配置）
1. `RidConfig::ReceiveTimeoutMs = 3000`
2. `RidConfig::MatchWindowMs = 1200`
3. `RidConfig::LegalHoldMs = 2000`
4. `RidConfig::ReconfirmWindowMs = 1200`

## 3. 运行规则
### 3.1 正常接收
- 在接收有效窗口内：RID 维持 `MATCHED/RECEIVED`（取决于轨迹匹配窗口）。

### 3.2 超时
- 超过 `ReceiveTimeoutMs`：RID 进入 `EXPIRED`。

### 3.3 合法保持（Legal Hold）
- 若上一稳定态为合法（`WL_ALLOWED`），且当前仅短时缺包，
  在 `LegalHoldMs` 内保持合法链，不立即打断。

### 3.4 再确认窗口（Reconfirm Window）
- 在 `ReconfirmWindowMs` 内重新收到合法身份包，可快速恢复合法状态。

### 3.5 回落
- 持续超时且超过保持/再确认窗口后，才回落到 `UNKNOWN/EXPIRED` 路径，
  并交由风险链继续判断是否进入可疑或高危。

## 4. 结果要求
1. 合法目标短时丢包不应瞬时触发高危。
2. 持续丢包必须回落，不能长期“伪合法”。
3. 恢复合法包后可快速回到合法链。
