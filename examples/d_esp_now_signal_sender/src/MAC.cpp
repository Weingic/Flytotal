#include <Arduino.h>
#include <WiFi.h>

namespace {
constexpr unsigned long PrintIntervalMs = 2000;
unsigned long lastPrintMs = 0;

void printMacAddress() {
  Serial.println();
  Serial.println("===== 本板（原 A 板）MAC 地址 =====");
  Serial.print("STA MAC: ");
  Serial.println(WiFi.macAddress());
  Serial.println();
  Serial.println("说明：当前使用 WIFI_STA 模式，ESP-NOW 测试时通常把这个 STA MAC 给 D 同学接收端。");
  Serial.println("下一步：记录这个地址后，切换到 esp_now_sender 环境发送 0xAA / 0x55。");
  Serial.println("=================================");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1000);

  WiFi.mode(WIFI_STA);

  printMacAddress();
  lastPrintMs = millis();
}

void loop() {
  unsigned long now = millis();
  if (now - lastPrintMs >= PrintIntervalMs) {
    printMacAddress();
    lastPrintMs = now;
  }
  delay(20);
}
