//射频模块

// 文件：lib/SafetyLink/SafetyLink.h
#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>

// 严格定义的【军工级指令结构体】（发什么指令，全靠这个包）
typedef struct struct_message {
    uint8_t cmd_type;     // 指令类型：1=最高级别开伞切电, 0=心跳包
    uint32_t timestamp;   // 纳秒/毫秒级时间戳，用于防重放攻击
} struct_message;

class SafetyLink {
private:
    uint8_t drone_mac[6]; // 无人机 (Node B) 的 MAC 地址
    esp_now_peer_info_t peerInfo;
    struct_message outgoingCmd;

public:
    SafetyLink();
    // 初始化网卡和射频协议
    bool init(uint8_t* target_mac);
    // 扣动扳机：发射救命指令！
    void fireParachute();
};