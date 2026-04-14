#include "GimbalPredictor.h"

#include "AppConfig.h"

GimbalPredictor::GimbalPredictor(float p, float d) {
    Kp = p;
    Kd = d;
    last_x = 0.0f;
    last_y = 0.0f;
    last_time = 0;
    current_pan_angle = GimbalConfig::CenterPanDeg;
}

float GimbalPredictor::calculateFiringAngle(float target_x, float target_y) {
    unsigned long now = millis();
    float dt = (now - last_time) / 1000.0f;
    if (dt <= 0.0f || dt > 1.0f) {
        dt = GimbalConfig::PredictorFallbackDtSeconds;
    }

    float vx = (target_x - last_x) / dt;
    float vy = (target_y - last_y) / dt;

    float predicted_x = target_x + (vx * GimbalConfig::PredictorLeadTimeSeconds);
    float predicted_y = target_y + (vy * GimbalConfig::PredictorLeadTimeSeconds);

    float target_angle = GimbalConfig::CenterPanDeg + (atan2(predicted_x, predicted_y) * 180.0f / PI);
    if (target_angle > GimbalConfig::MaxPanDeg) {
        target_angle = GimbalConfig::MaxPanDeg;
    }
    if (target_angle < GimbalConfig::MinPanDeg) {
        target_angle = GimbalConfig::MinPanDeg;
    }

    float error = target_angle - current_pan_angle;
    current_pan_angle += (Kp * error);

    last_x = target_x;
    last_y = target_y;
    last_time = now;

    return current_pan_angle;
}

float GimbalPredictor::getCurrentAngle() {
    return current_pan_angle;
}

void GimbalPredictor::setTunings(float p, float d) {
    Kp = p;
    Kd = d;
}
