import serial
import threading
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider
from collections import deque

# ================= 1. 串口配置 (必须修改为你自己的 COM 端口!) =================
SERIAL_PORT = 'COM4'  # Windows 可能是 COM3, COM4；Mac 可能是 /dev/cu.usbserial-xxx
BAUD_RATE = 115200

# 尝试打开串口
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"✅ 成功连接到 ESP32: {SERIAL_PORT}")
except Exception as e:
    print(f"❌ 串口打开失败，请检查 {SERIAL_PORT} 是否被占用或写错: {e}")
    exit()

# ================= 2. 数据队列 (窗口长度10秒) =================
WINDOW_SIZE = 500  # 500次 * 20ms = 10秒历史记录
t_data = deque(maxlen=WINDOW_SIZE)
tgt_x_data = deque(maxlen=WINDOW_SIZE)    # 雷达目标 X坐标 (毫米)
pan_angle_data = deque(maxlen=WINDOW_SIZE) # 舵机真实角度 (度)

start_time = time.time()

# ================= 3. 串口后台疯狂读取线程 =================
def read_serial_thread():
    while True:
        try:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                # 过滤并解析格式为 "DATA,1500.5,95.5" 的数据
                if line.startswith("DATA"):
                    parts = line.split(',')
                    if len(parts) >= 3:
                        tgt_x = float(parts[1])
                        pan = float(parts[2])
                        
                        t_now = time.time() - start_time
                        t_data.append(t_now)
                        tgt_x_data.append(tgt_x)
                        pan_angle_data.append(pan)
                else:
                    # 打印 ESP32 发来的普通调试信息 (比如发现目标、丢失目标)
                    if line: print(f"[ESP32] {line}")
        except Exception as e:
            pass

# 启动守护线程，完全不卡顿画图
threading.Thread(target=read_serial_thread, daemon=True).start()

# ================= 4. 画图面板初始化 (双 Y 轴黑科技) =================
plt.style.use('dark_background')
fig, ax1 = plt.subplots(figsize=(12, 6))
plt.subplots_adjust(left=0.1, bottom=0.35, right=0.9, top=0.9)
fig.canvas.manager.set_window_title('Hardware-in-the-Loop (HITL) Ground Station')

# 轴1 (左侧红轴)：云台角度 (度)
ax1.set_xlabel('Time (Seconds)')
ax1.set_ylabel('Pan Angle (Degrees)', color='r', fontsize=12)
line_pan, = ax1.plot([],[], 'r-', linewidth=2.5, label='Real SG90 Angle')
ax1.tick_params(axis='y', labelcolor='r')
ax1.set_ylim(30, 150) # 舵机的物理边界

# 轴2 (右侧白轴)：雷达横向距离 (毫米)
ax2 = ax1.twinx()
ax2.set_ylabel('Radar Target X (mm)', color='w', fontsize=12)
line_tgt, = ax2.plot([],[], 'w--', linewidth=2, alpha=0.8, label='LD2450 X Position')
ax2.tick_params(axis='y', labelcolor='w')
ax2.set_ylim(-3000, 3000) # LD2450 的典型横向视场范围

# 合并图例
lines =[line_tgt, line_pan]
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='upper right')
ax1.grid(True, linestyle=':', alpha=0.3)

# ================= 5. 交互滑块 (向下位机发号施令) =================
axcolor = 'lightgoldenrodyellow'
ax_kp = plt.axes([0.15, 0.15, 0.70, 0.04], facecolor=axcolor)
ax_kd = plt.axes([0.15, 0.05, 0.70, 0.04], facecolor=axcolor)

slider_kp = Slider(ax_kp, 'Hardware Kp', 0.0, 1.5, valinit=0.6, valstep=0.01)
slider_kd = Slider(ax_kd, 'Hardware Kd', 0.0, 0.5, valinit=0.05, valstep=0.01)

# 当滑块拖动时，通过串口将数据发送给真实的 ESP32！
def update_kp(val):
    ser.write(f"KP,{val:.2f}\n".encode('utf-8'))
def update_kd(val):
    ser.write(f"KD,{val:.2f}\n".encode('utf-8'))

slider_kp.on_changed(update_kp)
slider_kd.on_changed(update_kd)

# ================= 6. 动画引擎 =================
def update_plot(frame):
    if len(t_data) > 2:
        # 更新线条数据
        line_pan.set_data(t_data, pan_angle_data)
        line_tgt.set_data(t_data, tgt_x_data)
        
        # 动态滚动 X 轴 (始终显示最近的10秒)
        current_time = t_data[-1]
        ax1.set_xlim(max(0, current_time - (WINDOW_SIZE * 0.02)), current_time + 0.5)
        
    return line_pan, line_tgt

ani = animation.FuncAnimation(fig, update_plot, interval=50, blit=False, cache_frame_data=False)
plt.show()