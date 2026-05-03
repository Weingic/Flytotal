#pragma once

#include <Arduino.h>

#include "SharedData.h"

namespace Fusion {

void updateFusionFields(SystemData &data, unsigned long now);
void printDebug(const SystemData &snapshot, Print &out);

}  // namespace Fusion
