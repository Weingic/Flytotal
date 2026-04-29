# D ESP-NOW 模拟发送端

用途：配合 D 同学接收板测试 ESP-NOW 指令链路。

这个示例是独立 PlatformIO 小工程，不会参与主工程 `src/main.cpp` 编译，避免和主固件的 `setup()` / `loop()` 冲突。

## 先读取这块旧 A 板的 MAC

默认环境是 `mac_reader`，会编译 `src/MAC.cpp`。

烧录后打开串口监视器，记录输出里的 `STA MAC`。ESP-NOW 在这里使用 `WIFI_STA` 模式，所以配合 D 同学接收端时，通常要给对方这个 `STA MAC`。

如果使用命令行：

```powershell
pio run -e mac_reader -t upload
pio device monitor -e mac_reader
```

## 使用前检查

当前已记录：

- D 接收板 MAC：`AC:A7:04:BF:4F:C0`
- 本板（原 A 板）STA MAC：`E8:3D:C1:F2:E6:B8`

检查项：

1. 切到 `esp_now_sender` 环境发送模拟信号。
2. 当前信道固定为 `1`，需要和 D 同学接收端保持一致。
3. 串口监视器波特率为 `115200`。

如果使用命令行烧录发送端：

```powershell
pio run -e esp_now_sender -t upload
pio device monitor -e esp_now_sender
```

## 串口指令

- `o`：发送 `0xAA`，模拟开伞/应急触发。
- `l`：发送 `0x55`，模拟锁伞/复位。
- `a`：自动测试，先发送开伞，等待 3 秒，再发送锁伞。

D 端如果开启 ACK 回传，发送端串口会打印：

- `ACK_OPEN_DONE`
- `ACK_LOCK_DONE`
- `ACK_ALREADY_OPEN`
- `ACK_ALREADY_LOCKED`
- `ACK_UNKNOWN_CMD`
