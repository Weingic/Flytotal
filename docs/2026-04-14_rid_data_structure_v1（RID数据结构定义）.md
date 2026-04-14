# 2026-04-14 RID 数据结构定义 V1

## 1. 目标
固定身份链输入字段，确保 Node A、桥接、网页三端字段一致。

## 2. 标准字段（V1）

| 字段名 | 类型 | 说明 | 是否必填 |
|---|---|---|---|
| `rid_id` | string | 身份 ID | 是 |
| `device_type` | string | 设备类型（如 UAV） | 是 |
| `source` | string | 身份来源（如 RID_SIM / NODE_B） | 是 |
| `timestamp_ms` | uint64 | 身份包时间戳（ms） | 是 |
| `auth_status` | string | 鉴权状态（如 VALID / INVALID） | 是 |
| `whitelist_tag` | string | 白名单标签（如 WL_OK / DENY / PENDING） | 是 |
| `signal_strength` | int | 信号强度（可选） | 否 |

## 3. 固件内部镜像字段（当前实现）
1. `rid_id`
2. `rid_device_type`
3. `rid_source`
4. `rid_auth_status`
5. `rid_whitelist_tag`
6. `rid_signal_strength`
7. `rid_whitelist_hit`
8. `rid_last_update_ms`
9. `rid_last_match_ms`
10. `rid_status`

## 4. 串口接入命令格式
```text
RID,MSG,rid_id,device_type,source,timestamp_ms,auth_status,whitelist_tag[,signal_strength]
```

示例：
```text
RID,MSG,SIM-RID-001,UAV,RID_SIM,1712880000000,VALID,WL_OK,-48
```

## 5. 查询命令
```text
RID,STATUS
```

可返回：
1. 当前 `rid_status`
2. 白名单命中
3. 最近更新 / 最近匹配时间
4. 当前身份包关键字段
