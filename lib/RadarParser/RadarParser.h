//雷达解析防抖

//功能：逐字节啃串口数据，防止粘包，提取出干净的 X 和 Y

#pragma once
#include <Arduino.h>
#include <SimpleKalmanFilter.h>

// 真实 LD2450 的四步帧头状态
enum ProtocolState { WAIT_AA, WAIT_FF, WAIT_03, WAIT_00, READ_DATA };

class RadarParser {
private:
    ProtocolState rxState;
    uint8_t buf[20];
    int buf_idx;
    
    float smooth_x;
    float smooth_y;
    
    // ⭐️ 核心武器：内置两个卡尔曼滤波器！
    SimpleKalmanFilter xKalman;
    SimpleKalmanFilter yKalman;

public:
    RadarParser();
    bool feedByte(uint8_t byteIn);
    float getParsedX();
    float getParsedY();
};