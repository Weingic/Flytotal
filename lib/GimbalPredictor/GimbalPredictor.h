#pragma once

#include <Arduino.h>
#include <math.h>

class GimbalPredictor {
private:
    float Kp;
    float Kd;
    float last_x;
    float last_y;
    unsigned long last_time;
    float current_pan_angle;

public:
    GimbalPredictor(float p, float d);
    float calculateFiringAngle(float target_x, float target_y);
    float getCurrentAngle();
    void setTunings(float p, float d);
};
