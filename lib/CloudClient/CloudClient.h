#pragma once

#include <Arduino.h>

namespace CloudClientLimits {
constexpr size_t EventIdSize = 32;
constexpr size_t VerdictSize = 40;
constexpr size_t RiskLevelSize = 16;
constexpr size_t FusionStageSize = 16;
constexpr size_t VisionLabelSize = 24;
constexpr size_t RidIdSize = 32;
constexpr size_t WlStatusSize = 16;
constexpr size_t ThreatLevelSize = 16;
constexpr size_t AssessmentSize = 96;
constexpr size_t ActionSize = 64;
constexpr size_t AlertTextSize = 128;
constexpr size_t CommandTypeSize = 32;
constexpr size_t CommandModeSize = 16;
constexpr size_t CommandReasonSize = 64;
constexpr size_t ErrorSize = 96;
constexpr uint32_t HttpTimeoutMs = 5000;
constexpr size_t ResponseBufferSize = 6144;
}

struct CloudSensingEvent {
    char event_id[CloudClientLimits::EventIdSize];
    char target_verdict[CloudClientLimits::VerdictSize];
    char risk_level[CloudClientLimits::RiskLevelSize];
    char fusion_stage[CloudClientLimits::FusionStageSize];
    float ld2450_x_mm;
    float ld2450_y_mm;
    float ld2450_vx_mm_s;
    float ld2450_vy_mm_s;
    float ld2451_range_m;
    float ld2451_speed_mps;
    float vision_confidence;
    char vision_label[CloudClientLimits::VisionLabelSize];
    char rid_id[CloudClientLimits::RidIdSize];
    char wl_status[CloudClientLimits::WlStatusSize];
    float multirotor_score;
    bool is_multirotor_like;
};

struct CloudAssessmentResult {
    bool ok;
    bool parsed;
    int http_status;
    int esp_error;
    unsigned long latency_ms;
    char threat_level[CloudClientLimits::ThreatLevelSize];
    char assessment[CloudClientLimits::AssessmentSize];
    char action[CloudClientLimits::ActionSize];
    char alert_text[CloudClientLimits::AlertTextSize];
    char command_type[CloudClientLimits::CommandTypeSize];
    float command_threshold_value;
    char command_mode[CloudClientLimits::CommandModeSize];
    char command_reason[CloudClientLimits::CommandReasonSize];
    char error[CloudClientLimits::ErrorSize];
};

class CloudClient {
public:
    CloudClient(const char *endpoint, const char *model, const char *api_key);

    bool hasCredentials() const;
    bool assess(const CloudSensingEvent &event, CloudAssessmentResult &result) const;

    static void buildTestEvent(CloudSensingEvent &event);

private:
    const char *endpoint_;
    const char *model_;
    const char *api_key_;

    bool buildRequestBody(const CloudSensingEvent &event, char *buffer, size_t buffer_size, CloudAssessmentResult &result) const;
    bool parseResponse(const char *response, CloudAssessmentResult &result) const;
};
