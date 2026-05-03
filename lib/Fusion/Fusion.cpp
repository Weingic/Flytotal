#include "Fusion.h"

#include <math.h>
#include <string.h>

#include "AppConfig.h"

namespace {

unsigned long highCandidateSinceMs = 0;

void copyField(char *destination, size_t destination_size, const char *value) {
    if (destination == nullptr || destination_size == 0) {
        return;
    }
    if (value == nullptr || value[0] == '\0') {
        value = "NONE";
    }
    strncpy(destination, value, destination_size - 1);
    destination[destination_size - 1] = '\0';
}

bool isNodeBOnline(const SystemData &snapshot, unsigned long now) {
    return snapshot.nodeb_last_update_ms > 0 &&
           (now - snapshot.nodeb_last_update_ms) <= NodeBConfig::StaleTimeoutMs &&
           strcmp(snapshot.nodeb_status, "OFFLINE_OR_TIMEOUT") != 0;
}

bool isLd2451Fresh(const SystemData &snapshot, unsigned long now) {
    return snapshot.ld2451_valid &&
           snapshot.ld2451_last_update_ms > 0 &&
           (now - snapshot.ld2451_last_update_ms) <= FarRadarConfig::StaleTimeoutMs;
}

bool computeFarMotionTrigger(const SystemData &snapshot, unsigned long now) {
    if (!isLd2451Fresh(snapshot, now)) {
        return false;
    }
    const float absSpeed = fabsf(snapshot.ld2451_speed_mps);
    return snapshot.ld2451_approach &&
           snapshot.ld2451_range_m >= FarRadarConfig::MinTriggerRangeM &&
           snapshot.ld2451_range_m <= FarRadarConfig::MaxTriggerRangeM &&
           absSpeed >= FarRadarConfig::MinAbsSpeedMps;
}

bool isLimitedVisionEnvironment(const SystemData &snapshot) {
    return strcmp(snapshot.environment_mode, "LOW_LIGHT") == 0 ||
           strcmp(snapshot.environment_mode, "FOG_OR_BLUR") == 0 ||
           strcmp(snapshot.environment_mode, "VISION_LOST") == 0;
}

void deriveVisionQuality(const SystemData &snapshot, char *destination, size_t destination_size) {
    if (strcmp(snapshot.environment_mode, "VISION_LOST") == 0) {
        copyField(destination, destination_size, "VISION_LOST");
        return;
    }
    if (strcmp(snapshot.environment_mode, "LOW_LIGHT") == 0 ||
        strcmp(snapshot.environment_mode, "FOG_OR_BLUR") == 0) {
        copyField(destination, destination_size, snapshot.vision_locked ? "DEGRADED_LOCKED" : "DEGRADED_VISUAL");
        return;
    }
    if (snapshot.vision_locked) {
        copyField(destination, destination_size, "CLEAR_LOCKED");
    } else if (snapshot.vision_state == VISION_SEARCHING) {
        copyField(destination, destination_size, "SEARCHING");
    } else if (snapshot.vision_state == VISION_LOST) {
        copyField(destination, destination_size, "VISION_LOST");
    } else {
        copyField(destination, destination_size, "NO_VISUAL");
    }
}

float radarRangeMm(const RadarTrack &track) {
    return sqrtf(track.x_mm * track.x_mm + track.y_mm * track.y_mm);
}

bool computeRangeAgreement(const SystemData &snapshot, bool ld2451Fresh) {
    if (!snapshot.radar_track.is_confirmed || !ld2451Fresh) {
        return false;
    }
    const float nearRangeMm = radarRangeMm(snapshot.radar_track);
    const float farRangeMm = snapshot.ld2451_range_m * 1000.0f;
    if (nearRangeMm < 100.0f || farRangeMm < 100.0f) {
        return false;
    }
    const float pct = fabsf(nearRangeMm - farRangeMm) * 100.0f / farRangeMm;
    return pct <= FusionConfig::RangeAgreementPct;
}

bool computeSpeedAgreement(const SystemData &snapshot, bool ld2451Fresh) {
    if (!snapshot.radar_track.is_confirmed || !ld2451Fresh) {
        return false;
    }
    const RadarTrack &track = snapshot.radar_track;
    const float range = radarRangeMm(track);
    if (range < 100.0f) {
        return false;
    }
    const float radialMmS = (track.x_mm * track.vx_mm_s + track.y_mm * track.vy_mm_s) / range;
    const float ldAbsMmS = fabsf(snapshot.ld2451_speed_mps * 1000.0f);
    const bool directionOk = snapshot.ld2451_approach ? radialMmS <= FusionConfig::SpeedAgreementMmS
                                                      : radialMmS >= -FusionConfig::SpeedAgreementMmS;
    return directionOk && fabsf(fabsf(radialMmS) - ldAbsMmS) <= FusionConfig::SpeedAgreementMmS;
}

const char *stageForRange(float rangeM, bool hasRange) {
    if (!hasRange) {
        return "NONE";
    }
    if (rangeM > FusionConfig::FarStageMinM) {
        return "FAR";
    }
    if (rangeM >= FusionConfig::MidStageMinM) {
        return "MID";
    }
    return "NEAR";
}

void updateHighHold(bool highCandidate, unsigned long now) {
    if (!highCandidate) {
        highCandidateSinceMs = 0;
        return;
    }
    if (highCandidateSinceMs == 0) {
        highCandidateSinceMs = now;
    }
}

bool highHoldSatisfied(unsigned long now) {
    return highCandidateSinceMs > 0 && (now - highCandidateSinceMs) >= FusionConfig::HighHoldWindowMs;
}

}  // namespace

namespace Fusion {

void updateFusionFields(SystemData &data, unsigned long now) {
    data.nodeb_online = isNodeBOnline(data, now);
    data.far_motion_trigger = computeFarMotionTrigger(data, now);

    if (data.environment_mode[0] == '\0') {
        copyField(data.environment_mode, sizeof(data.environment_mode), "CLEAR");
    }
    deriveVisionQuality(data, data.vision_quality, sizeof(data.vision_quality));

    const bool ld2451Fresh = isLd2451Fresh(data, now);
    const bool nearRadar = data.radar_track.is_confirmed;
    const bool farRadar = data.far_motion_trigger;
    const bool ridActive = data.rid_status == RID_RECEIVED ||
                           data.rid_status == RID_MATCHED ||
                           data.rid_status == RID_INVALID;
    const bool ridMatched = data.rid_status == RID_MATCHED;
    const bool visualActive = data.vision_locked || data.vision_state == VISION_LOCKED;

    data.range_agreement = computeRangeAgreement(data, ld2451Fresh);
    data.speed_agreement = computeSpeedAgreement(data, ld2451Fresh);
    data.vision_agreement = visualActive && nearRadar;

    uint8_t votes = 0;
    if (nearRadar) {
        votes++;
    }
    if (farRadar) {
        votes++;
    }
    if (ridActive) {
        votes++;
    }
    if (visualActive) {
        votes++;
    }
    data.source_vote_count = votes;

    const float radarRangeM = nearRadar ? radarRangeMm(data.radar_track) / 1000.0f : 0.0f;
    const bool hasStageRange = ld2451Fresh || nearRadar;
    const float stageRangeM = ld2451Fresh ? data.ld2451_range_m : radarRangeM;
    const char *stage = stageForRange(stageRangeM, hasStageRange);
    copyField(data.fusion_stage, sizeof(data.fusion_stage), stage);

    const bool twoSourceCandidate = votes >= 2;
    const bool consistencyOk = data.range_agreement || data.speed_agreement || ridActive || visualActive;
    const bool highCandidate = twoSourceCandidate && consistencyOk;
    updateHighHold(highCandidate, now);
    const bool highAllowed = highHoldSatisfied(now);

    const bool limitedVision = isLimitedVisionEnvironment(data);
    const char *level = "NONE";
    const char *reason = "NONE";

    if (!FusionConfig::Enabled) {
        if (votes >= 3) {
            level = "HIGH";
        } else if (votes == 2) {
            level = "MID";
        } else if (votes == 1) {
            level = "LOW";
        }
        reason = "LEGACY_SOURCE_COUNT";
    } else if (strcmp(stage, "FAR") == 0) {
        if (farRadar && ridActive) {
            level = "MID";
            reason = "FAR_LD2451_RID";
        } else if (farRadar) {
            level = "LOW";
            reason = "FAR_LD2451_WARNING";
        } else if (ridActive) {
            level = "LOW";
            reason = "FAR_RID_ONLY";
        }
    } else if (strcmp(stage, "MID") == 0) {
        if (highAllowed && twoSourceCandidate) {
            level = "HIGH";
            reason = data.range_agreement ? "MID_RANGE_AGREEMENT" : "MID_MULTI_SOURCE";
        } else if (twoSourceCandidate) {
            level = "MID";
            reason = "MID_WAIT_WINDOW";
        } else if (votes == 1) {
            level = "LOW";
            reason = "MID_SINGLE_SOURCE";
        }
    } else if (strcmp(stage, "NEAR") == 0) {
        if (highAllowed && twoSourceCandidate && (visualActive || ridMatched)) {
            level = "HIGH";
            reason = visualActive ? "NEAR_VISUAL_CONFIRMED" : "NEAR_RID_MATCHED";
        } else if (twoSourceCandidate) {
            level = "MID";
            reason = "NEAR_NEEDS_VISUAL_OR_RID";
        } else if (votes == 1) {
            level = "LOW";
            reason = "NEAR_SINGLE_SOURCE";
        }
    } else if (votes > 0) {
        level = votes >= 2 ? "MID" : "LOW";
        reason = "NO_RANGE_MULTI_SOURCE";
    }

    if (data.rid_status == RID_INVALID) {
        reason = "IDENTITY_CONFLICT";
    } else if ((nearRadar || farRadar) && limitedVision && strcmp(level, "NONE") != 0) {
        reason = "RADAR_PRIMARY_VISUAL_LIMITED";
    }

    copyField(data.fusion_level, sizeof(data.fusion_level), level);
    copyField(data.fusion_reason, sizeof(data.fusion_reason), reason);

    float confidence = 0.0f;
    confidence += votes * 0.22f;
    confidence += data.range_agreement ? 0.12f : 0.0f;
    confidence += data.speed_agreement ? 0.10f : 0.0f;
    confidence += data.vision_agreement ? 0.10f : 0.0f;
    confidence += highAllowed ? 0.10f : 0.0f;
    if (strcmp(level, "NONE") == 0) {
        confidence = 0.0f;
    }
    if (confidence > 1.0f) {
        confidence = 1.0f;
    }
    data.fusion_confidence = confidence;
    data.is_multirotor_like = data.radar_track.is_multirotor_like;
    data.multirotor_score = data.radar_track.multirotor_score;
}

void printDebug(const SystemData &snapshot, Print &out) {
    out.print("FUSION,DEBUG,node=");
    out.print(NodeConfig::NodeId);
    out.print(",stage=");
    out.print(snapshot.fusion_stage[0] != '\0' ? snapshot.fusion_stage : "NONE");
    out.print(",level=");
    out.print(snapshot.fusion_level[0] != '\0' ? snapshot.fusion_level : "NONE");
    out.print(",confidence=");
    out.print(snapshot.fusion_confidence, 2);
    out.print(",votes=");
    out.print(snapshot.source_vote_count);
    out.print(",range_agreement=");
    out.print(snapshot.range_agreement ? 1 : 0);
    out.print(",speed_agreement=");
    out.print(snapshot.speed_agreement ? 1 : 0);
    out.print(",vision_agreement=");
    out.print(snapshot.vision_agreement ? 1 : 0);
    out.print(",window_ms=");
    out.print(highCandidateSinceMs > 0 ? millis() - highCandidateSinceMs : 0);
    out.print(",multirotor_like=");
    out.print(snapshot.is_multirotor_like ? 1 : 0);
    out.print(",multirotor_score=");
    out.print(snapshot.multirotor_score, 1);
    out.print(",speed_variance_mm_s=");
    out.print(snapshot.radar_track.speed_variance_mm_s, 1);
    out.print(",heading_rate_deg_s=");
    out.println(snapshot.radar_track.heading_rate_deg_s, 1);
}

}  // namespace Fusion
