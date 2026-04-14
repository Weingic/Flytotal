# 2026-04-14 网页 RID 展示验收 V1

## 1. 验收目标
网页端必须可见以下 3 项：
1. 当前 `rid_status`
2. 白名单命中状态
3. 最近身份更新时间

## 2. 实现位置
1. 页面：`tools/vision_dashboard.html`
2. 桥接：`tools/node_a_serial_bridge_NodeA串口桥接.py`
3. 固件输出：`src/main.cpp`（`printNormalizedStateFields` / `RID,STATUS`）

## 3. 页面字段映射

| 页面元素 ID | 来源字段 | 说明 |
|---|---|---|
| `nodeRidValue` | `rid_status` | 当前身份状态 |
| `nodeRidWhitelistValue` | `rid_whitelist_hit` | 白名单命中（HIT/MISS） |
| `nodeRidUpdateValue` | `rid_last_update_ms` + `rid_last_match_ms` | 最近更新时间 / 最近匹配时间 |

## 4. 验收步骤
1. 启动串口桥接：
```powershell
python tools/node_a_serial_bridge_NodeA串口桥接.py --port COM4 --baud 115200 --echo
```
2. 启动网页服务：
```powershell
python tools/vision_web_server_视觉网页服务.py --host 127.0.0.1 --port 8765
```
3. 打开页面：`http://127.0.0.1:8765`
4. 用 RID 模拟器切换三种模式，观察页面字段是否同步变化。

## 5. 通过口径
1. `RID normal` 时：
   - `RID = MATCHED`
   - `RID 白名单 = HIT`
2. `RID missing` 时：
   - `RID = NONE` 或 `EXPIRED`
   - `RID 白名单 = MISS`
3. `RID invalid` 时：
   - `RID = INVALID`
   - `RID 白名单 = MISS`
4. `RID 最近更新`字段有实时刷新。

## 6. 结论
网页 RID 状态展示链已满足 4.14 当天验收要求。
