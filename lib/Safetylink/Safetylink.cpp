// 文件：lib/SafetyLink/SafetyLink.cpp
#include "SafetyLink.h"

// ESP-NOW 强制要求的回调函数（必须是全局的），用于告诉你“子弹”有没有打中目标
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    Serial.print(">> [射频底层] 弹伞指令发送状态: ");
    Serial.println(status == ESP_NOW_SEND_SUCCESS ? "✅ 命中目标！" : "❌ 丢包！");
}

SafetyLink::SafetyLink() {}

bool SafetyLink::init(uint8_t* target_mac) {
    // 1. 把 Wi-Fi 设置为 STA 模式（ESP-NOW必须的基础环境）
    WiFi.mode(WIFI_STA);
    
    // 2. 初始化底层 ESP-NOW 协议栈
    if (esp_now_init() != ESP_OK) {
        Serial.println("❌ ESP-NOW 初始化灾难性失败！");
        return false;
    }
    
    // 3. 注册“子弹打中”的回调函数
    esp_now_register_send_cb(OnDataSent);
    
    // 4. 把无人机的 MAC 地址录入“火控雷达锁定系统”
    memcpy(drone_mac, target_mac, 6);
    memcpy(peerInfo.peer_addr, drone_mac, 6);
    peerInfo.channel = 0;     // 默认信道
    peerInfo.encrypt = false; // 抢时间！不加密，直接裸奔发射
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK){
        Serial.println("❌ 无法锁定无人机 MAC 地址！");
        return false;
    }
    
    Serial.println("✅ 安全通讯链路已建立，随时可以击发！");
    return true;
}

void SafetyLink::fireParachute() {
    // 封装致命指令
    outgoingCmd.cmd_type = 1; // 1 代表 EMERGENCY_PARACHUTE
    outgoingCmd.timestamp = millis();
    
    // 瞬间注入 MAC 层发送！
    esp_err_t result = esp_now_send(drone_mac, (uint8_t *) &outgoingCmd, sizeof(outgoingCmd));
    
    if (result == ESP_OK) {
        Serial.println("🚀 [致命干预] 伞舱互锁指令已击发！耗时 < 1ms！");
    } else {
        Serial.println("⚠️ 击发失败！");
    }
}