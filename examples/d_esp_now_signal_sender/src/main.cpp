#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#if __has_include(<esp_arduino_version.h>)
#include <esp_arduino_version.h>
#endif

// 修改这里：填 D 同学接收板的 MAC 地址。
// 当前 D 接收板 MAC：AC:A7:04:BF:4F:C0
// 当前本板（原 A 板）STA MAC：E8:3D:C1:F2:E6:B8
uint8_t D_RECEIVER_MAC[] = {0xAC, 0xA7, 0x04, 0xBF, 0x4F, 0xC0};

constexpr uint8_t CMD_OPEN = 0xAA;
constexpr uint8_t CMD_LOCK = 0x55;
constexpr uint8_t ESP_NOW_CHANNEL = 1;

unsigned long lastReadyPrintMs = 0;

void onSend(const uint8_t *mac_addr, esp_now_send_status_t status) {
    (void)mac_addr;
    Serial.print("[SEND_CB] 发送状态：");
    if (status == ESP_NOW_SEND_SUCCESS) {
        Serial.println("成功");
    } else {
        Serial.println("失败");
    }
}

void printMac(const uint8_t *mac) {
    if (mac == nullptr) {
        Serial.print("NULL");
        return;
    }

    for (int i = 0; i < 6; i++) {
        if (mac[i] < 16) {
            Serial.print("0");
        }
        Serial.print(mac[i], HEX);
        if (i < 5) {
            Serial.print(":");
        }
    }
}

void printAckPayload(const uint8_t *data, int len) {
    if (data == nullptr || len <= 0) {
        Serial.println("空 ACK");
        return;
    }

    Serial.write(data, len);
    Serial.println();
}

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    const uint8_t *mac = info != nullptr ? info->src_addr : nullptr;
    Serial.print("[ACK_RECV] 来自 ");
    printMac(mac);
    Serial.print(" 内容：");
    printAckPayload(data, len);
}
#else
void onReceive(const uint8_t *mac, const uint8_t *data, int len) {
    Serial.print("[ACK_RECV] 来自 ");
    printMac(mac);
    Serial.print(" 内容：");
    printAckPayload(data, len);
}
#endif

void sendCommand(uint8_t cmd) {
    uint8_t payload[1] = {cmd};
    esp_err_t result = esp_now_send(D_RECEIVER_MAC, payload, sizeof(payload));

    Serial.print("[SEND] 指令 0x");
    Serial.print(cmd, HEX);
    Serial.print(" -> ");

    if (result == ESP_OK) {
        Serial.println("已提交发送");
    } else {
        Serial.print("发送失败，错误码：");
        Serial.println(result);
    }
}

void setup() {
    Serial.begin(115200);
    unsigned long serialWaitStartMs = millis();
    while (!Serial && millis() - serialWaitStartMs < 3000) {
        delay(10);
    }
    delay(500);

    Serial.println();
    Serial.println("===== ESP-NOW 模拟发送端启动 =====");

    WiFi.mode(WIFI_STA);

    // 固定信道为 1，和 D 同学代码保持一致。
    esp_wifi_set_channel(ESP_NOW_CHANNEL, WIFI_SECOND_CHAN_NONE);

    Serial.print("本机 MAC 地址：");
    Serial.println(WiFi.macAddress());

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW 初始化失败");
        return;
    }

    esp_now_register_send_cb(onSend);
    esp_now_register_recv_cb(onReceive);

    esp_now_peer_info_t peerInfo;
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, D_RECEIVER_MAC, 6);
    peerInfo.channel = ESP_NOW_CHANNEL;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("添加 D 接收端失败，请检查 MAC 地址");
        return;
    }

    Serial.println("已添加 D 接收端");
    Serial.println();
    Serial.println("串口输入指令：");
    Serial.println("o ：发送 0xAA，模拟开伞/应急触发");
    Serial.println("l ：发送 0x55，模拟锁伞/复位");
    Serial.println("a ：自动测试：开伞 -> 等待3秒 -> 锁伞");
    Serial.println("================================");
}

void loop() {
    unsigned long now = millis();
    if (now - lastReadyPrintMs >= 2000) {
        lastReadyPrintMs = now;
        Serial.print("[READY] ESP-NOW sender alive, local_mac=");
        Serial.print(WiFi.macAddress());
        Serial.print(", target_d_mac=AC:A7:04:BF:4F:C0");
        Serial.println(", input o/l/a then Enter");
    }

    if (Serial.available()) {
        char ch = Serial.read();

        if (ch == 'o' || ch == 'O') {
            Serial.println("[TEST] 发送开伞指令 0xAA");
            sendCommand(CMD_OPEN);
        } else if (ch == 'l' || ch == 'L') {
            Serial.println("[TEST] 发送锁伞指令 0x55");
            sendCommand(CMD_LOCK);
        } else if (ch == 'a' || ch == 'A') {
            Serial.println("[TEST] 自动测试开始");

            Serial.println("[STEP 1] 发送开伞指令");
            sendCommand(CMD_OPEN);

            delay(3000);

            Serial.println("[STEP 2] 发送锁伞指令");
            sendCommand(CMD_LOCK);

            Serial.println("[TEST] 自动测试结束");
        }
    }

    delay(20);
}
