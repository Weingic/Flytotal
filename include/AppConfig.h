#pragma once

namespace AppSerialConfig {
constexpr unsigned long MonitorBaudRate = 115200;
constexpr unsigned long RadarBaudRate = 256000;
constexpr int RadarRxPin = 18;
constexpr int RadarTxPin = 17;
constexpr unsigned long StartupDelayMs = 2000;
}

namespace NodeConfig {
constexpr const char *NodeId = "A1";
constexpr const char *NodeRole = "EDGE";
constexpr const char *NodeZone = "ZONE_NORTH";
constexpr const char *BaselineVersion = "Node_A_Base_Demo_V1.1";
}

namespace GimbalConfig {
constexpr float PredictorKp = 0.45f;
constexpr float PredictorKd = 0.05f;
constexpr float PredictorFallbackDtSeconds = 0.02f;
constexpr float PredictorLeadTimeSeconds = 0.00f;
constexpr float CenterPanDeg = 90.0f;
constexpr float CenterTiltDeg = 90.0f;
constexpr float MinPanDeg = 10.0f;
constexpr float MaxPanDeg = 170.0f;
constexpr float ScanningAmplitudeDeg = 15.0f;
constexpr float ScanningPeriodDivisor = 900.0f;
constexpr long MinTiltMapInputMm = 0;
constexpr long MaxTiltMapInputMm = 6000;
constexpr long MinTiltDeg = 60;
constexpr long MaxTiltDeg = 120;
}

namespace ServoConfig {
constexpr int PanPin = 4;
constexpr int TiltPin = 5;
constexpr int PwmFrequencyHz = 50;
constexpr int PulseMinUs = 500;
constexpr int PulseMaxUs = 2500;
}

namespace RadarConfig {
constexpr float LockDistanceThresholdMm = 500.0f;
constexpr unsigned long PollDelayMs = 10;
}

namespace TrackConfig {
constexpr uint16_t ConfirmFrames = 5;
constexpr unsigned long LostTimeoutMs = 250;
constexpr unsigned long RebuildGapMs = 400;
}

namespace HunterConfig {
constexpr float TrackingBaseScore = 10.0f;
constexpr float PersistenceScorePerSeen = 3.0f;
constexpr float PersistenceScoreMax = 24.0f;
constexpr float ConfirmedBonusScore = 8.0f;
constexpr float RidMatchedScore = -25.0f;
constexpr float RidReceivedScore = 8.0f;
constexpr float RidNoneScore = 24.0f;
constexpr float RidExpiredScore = 28.0f;
constexpr float RidInvalidScore = 34.0f;
// Backward-compatible aliases used by existing logs/scripts.
constexpr float RidUnknownScore = RidReceivedScore;
constexpr float RidMissingScore = RidNoneScore;
constexpr float RidSuspiciousScore = RidInvalidScore;
constexpr float ProximityScore = 12.0f;
constexpr float MotionAnomalyScore = 12.0f;
constexpr float ProximityThresholdMm = 1500.0f;
constexpr float MotionAnomalySpeedThresholdMmS = 350.0f;
constexpr float SuspiciousThreshold = 40.0f;
constexpr float HighRiskThreshold = 60.0f;
constexpr float EventThreshold = 80.0f;
constexpr unsigned long SuspiciousEnterHoldMs = 120;
constexpr unsigned long HighRiskEnterHoldMs = 250;
constexpr unsigned long EventEnterHoldMs = 500;
constexpr unsigned long SuspiciousExitHoldMs = 500;
constexpr unsigned long HighRiskExitHoldMs = 700;
constexpr unsigned long EventExitHoldMs = 900;
}

namespace RidConfig {
constexpr unsigned long MatchWindowMs = 1200;
constexpr unsigned long ReceiveTimeoutMs = 3000;
constexpr unsigned long LegalHoldMs = 2000;
constexpr unsigned long ReconfirmWindowMs = 1200;
}

namespace TrackingConfig {
constexpr unsigned long AcquireConfirmMs = 150;
constexpr unsigned long LostRecoveryTimeoutMs = 3000;
constexpr unsigned long LoopDelayMs = 20;
}

namespace CloudConfig {
constexpr unsigned long HeartbeatMs = 1000;
constexpr unsigned long EventReportMs = 250;
}

namespace EventConfig {
// A short no-RID appearance is treated as suspicious, but must not be eventized immediately.
constexpr unsigned long MissingRidEventMinDurationMs = 800;
}
