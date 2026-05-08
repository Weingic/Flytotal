#pragma once

#include <Arduino.h>
#include <math.h>

class GimbalPredictor {
private:
    float Kp;
    float Kd;
    float last_x;
    float last_y;
    float last_vx;
    float last_vy;
    float filtered_ax;
    float filtered_ay;
    unsigned long last_time;
    float current_pan_angle;

public:
    GimbalPredictor(float p, float d);
    float calculateFiringAngle(float target_x, float target_y);
    float getCurrentAngle();
    void setTunings(float p, float d);
};
