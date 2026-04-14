//雷达解析防抖
#include "RadarParser.h"

// 构造函数：初始化状态机，并设置卡尔曼滤波参数防抖！
RadarParser::RadarParser() : xKalman(5, 2, 0.4), yKalman(5, 2, 0.4) {
    rxState = WAIT_AA;  //当前执行到哪一步了
    buf_idx = 0;         //临时缓存收到的字节
    smooth_x = 0;       
    smooth_y = 0;          //两个Kalman滤波器
}                //                调参数2

// 军工级防断帧状态机：精准锁定 AA FF 03 00 帧头
bool RadarParser::feedByte(uint8_t b) {
    switch (rxState) {
        case WAIT_AA: if (b == 0xAA) rxState = WAIT_FF; break;
        case WAIT_FF: if (b == 0xFF) rxState = WAIT_03; else rxState = WAIT_AA; break;
        case WAIT_03: if (b == 0x03) rxState = WAIT_00; else rxState = WAIT_AA; break;
        case WAIT_00: if (b == 0x00) { rxState = READ_DATA; buf_idx = 0; } else rxState = WAIT_AA; break;
        
        case READ_DATA:
            buf[buf_idx++] = b;
            // 只要凑齐 8 个字节，就已经包含了我们要的 X 和 Y！
            if (buf_idx >= 8) { 
                // ==========================================
                // 🎯 【提取真实的 X 轴坐标】 (buf[0] 和 buf[1])
                // ==========================================
                bool x_is_negative = (buf[1] & 0x80) != 0; // 最高位是符号位
                int16_t raw_x = ((buf[1] & 0x7F) << 8) | buf[0];
                if (x_is_negative) raw_x = -raw_x; 
                smooth_x = xKalman.updateEstimate((float)raw_x); // 丢进卡尔曼去噪

                // ==========================================
                // 🎯 【提取真实的 Y 轴距离】 (buf[2] 和 buf[3])
                // ==========================================
                int16_t raw_y = ((buf[3] & 0x7F) << 8) | buf[2]; 
                smooth_y = yKalman.updateEstimate((float)raw_y); // 丢进卡尔曼去噪

                rxState = WAIT_AA; // 重置状态，准备抓取下一帧
                return true;       // 成功拿到真实物理坐标，通知大脑开火！
            }
            break;
    }
    return false;
}

float RadarParser::getParsedX() { return smooth_x; }
float RadarParser::getParsedY() { return smooth_y; }