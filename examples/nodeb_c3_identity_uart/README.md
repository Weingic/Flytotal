# NodeB C3 Identity UART Sender

This standalone PlatformIO project is for the current `NodeA + NodeB` dual-node hardware test.

## Role

- `NodeA`: ESP32-S3 main sensing node, running the root Flytotal firmware.
- `NodeB`: ESP32-C3 auxiliary identity-chain node, running this example.

This is not the full `A1 + A2` two-complete-sensing-node deployment. `A1 + A2` remains a later expansion/demo layer.

## Wiring

Default pins:

```text
NodeB ESP32-C3 GPIO4 TX  ->  NodeA ESP32-S3 GPIO15 RX
NodeB ESP32-C3 GPIO5 RX  <-  NodeA ESP32-S3 GPIO16 TX   optional
NodeB ESP32-C3 GND       ->  NodeA ESP32-S3 GND
```

Recommended power during first test:

```text
NodeA and NodeB use separate USB power.
Only GND is shared.
```

## Protocol Sent To NodeA

NodeB sends clean text lines on UART1. The default RID is a cooperative demo
identity already present in NodeA's whitelist table:

```text
NODEB,HEARTBEAT,node=B1,source=BLE_WIFI,status=OK,rssi=-62,ble=1,wifi=1
NODEB,RID,node=B1,source=BLE,rssi=-62,status=SEEN,id=SIM-RID-001,auth_status=VALID,whitelist_tag=WL_OK
NODEB,OFFLINE
```

NodeA already accepts these lines through `Serial2`.

## USB Monitor Commands

Open the C3 serial monitor and type:

```text
h  send one heartbeat
r  send one RID event
o  send one offline event
a  toggle automatic RID events
?  print help
```

Heartbeat is always sent once per second. RID is sent every three seconds while auto RID is enabled.

## Demo Identity

The default build uses:

```text
NODEB_RID_ID=SIM-RID-001
NODEB_RID_AUTH_STATUS=VALID
NODEB_RID_WHITELIST_TAG=WL_OK
```

With the current NodeA whitelist, this should produce:

```text
wl_status=WL_ALLOWED
rid_whitelist_hit=1
target_verdict=CONFIRMED_COOPERATIVE_DRONE
event_active=0
```

## Build

```powershell
pio run -d examples/nodeb_c3_identity_uart
```

Flash with the same project folder selected in PlatformIO, or specify the upload
port explicitly:

```powershell
pio run -d examples/nodeb_c3_identity_uart -t upload --upload-port COM6
```
