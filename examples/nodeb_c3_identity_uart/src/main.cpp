#include <Arduino.h>
#include <WiFi.h>

#ifndef NODEB_NODE_ID
#define NODEB_NODE_ID "B1"
#endif

#ifndef NODEA_UART_TX_PIN
#define NODEA_UART_TX_PIN 4
#endif

#ifndef NODEA_UART_RX_PIN
#define NODEA_UART_RX_PIN 5
#endif

#ifndef NODEA_UART_BAUD
#define NODEA_UART_BAUD 115200
#endif

#ifndef NODEB_RID_ID
#define NODEB_RID_ID "SIM-RID-001"
#endif

#ifndef NODEB_RID_AUTH_STATUS
#define NODEB_RID_AUTH_STATUS "VALID"
#endif

#ifndef NODEB_RID_WHITELIST_TAG
#define NODEB_RID_WHITELIST_TAG "WL_OK"
#endif

namespace {

HardwareSerial NodeALink(1);

constexpr unsigned long HeartbeatIntervalMs = 1000;
constexpr unsigned long RidIntervalMs = 3000;
constexpr int BaseRssi = -62;

unsigned long lastHeartbeatMs = 0;
unsigned long lastRidMs = 0;
bool autoRidEnabled = true;

int simulatedRssi(unsigned long now) {
    const int wobble = static_cast<int>((now / 1000UL) % 7UL) - 3;
    return BaseRssi + wobble;
}

void writeNodeALine(const char *line) {
    NodeALink.println(line);
    Serial.print("[NODEA_TX] ");
    Serial.println(line);
}

void sendHeartbeat(unsigned long now) {
    char line[160];
    snprintf(
        line,
        sizeof(line),
        "NODEB,HEARTBEAT,node=%s,source=BLE_WIFI,status=OK,rssi=%d,ble=1,wifi=1",
        NODEB_NODE_ID,
        simulatedRssi(now)
    );
    writeNodeALine(line);
}

void sendRid(unsigned long now) {
    char line[192];
    snprintf(
        line,
        sizeof(line),
        "NODEB,RID,node=%s,source=BLE,rssi=%d,status=SEEN,id=%s,auth_status=%s,whitelist_tag=%s",
        NODEB_NODE_ID,
        simulatedRssi(now),
        NODEB_RID_ID,
        NODEB_RID_AUTH_STATUS,
        NODEB_RID_WHITELIST_TAG
    );
    writeNodeALine(line);
}

void sendOffline() {
    writeNodeALine("NODEB,OFFLINE");
}

void printHelp() {
    Serial.println();
    Serial.println("NodeB C3 identity UART sender");
    Serial.print("Node id: ");
    Serial.println(NODEB_NODE_ID);
    Serial.print("UART1 TX GPIO");
    Serial.print(NODEA_UART_TX_PIN);
    Serial.print(" -> NodeA RX, RX GPIO");
    Serial.print(NODEA_UART_RX_PIN);
    Serial.println(" <- NodeA TX optional");
    Serial.println("Commands: h=heartbeat, r=RID, o=offline, a=toggle auto RID, ?=help");
    Serial.print("RID demo identity: ");
    Serial.print(NODEB_RID_ID);
    Serial.print(" / ");
    Serial.print(NODEB_RID_AUTH_STATUS);
    Serial.print(" / ");
    Serial.println(NODEB_RID_WHITELIST_TAG);
    Serial.println();
}

void handleUsbCommand(char ch, unsigned long now) {
    if (ch == '\r' || ch == '\n' || ch == ' ') {
        return;
    }

    switch (ch) {
    case 'h':
    case 'H':
        sendHeartbeat(now);
        break;
    case 'r':
    case 'R':
        sendRid(now);
        break;
    case 'o':
    case 'O':
        sendOffline();
        break;
    case 'a':
    case 'A':
        autoRidEnabled = !autoRidEnabled;
        Serial.print("[NODEB] auto RID=");
        Serial.println(autoRidEnabled ? "ON" : "OFF");
        break;
    case '?':
        printHelp();
        break;
    default:
        Serial.print("[NODEB] unknown command: ");
        Serial.println(ch);
        printHelp();
        break;
    }
}

}  // namespace

void setup() {
    Serial.begin(115200);
    const unsigned long serialStartMs = millis();
    while (!Serial && millis() - serialStartMs < 2500) {
        delay(10);
    }

    NodeALink.begin(NODEA_UART_BAUD, SERIAL_8N1, NODEA_UART_RX_PIN, NODEA_UART_TX_PIN);

    WiFi.mode(WIFI_STA);
    delay(100);

    Serial.println();
    Serial.println("===== Flytotal NodeB C3 identity UART sender =====");
    Serial.print("Local WiFi MAC: ");
    Serial.println(WiFi.macAddress());
    printHelp();

    const unsigned long now = millis();
    sendHeartbeat(now);
    sendRid(now);
    lastHeartbeatMs = now;
    lastRidMs = now;
}

void loop() {
    const unsigned long now = millis();

    if (now - lastHeartbeatMs >= HeartbeatIntervalMs) {
        lastHeartbeatMs = now;
        sendHeartbeat(now);
    }

    if (autoRidEnabled && now - lastRidMs >= RidIntervalMs) {
        lastRidMs = now;
        sendRid(now);
    }

    while (Serial.available() > 0) {
        handleUsbCommand(static_cast<char>(Serial.read()), now);
    }

    delay(10);
}
