#include "CloudClient.h"

#include <cJSON.h>
#include <esp_crt_bundle.h>
#include <esp_http_client.h>
#include <string.h>

#ifndef esp_crt_bundle_attach
#define esp_crt_bundle_attach arduino_esp_crt_bundle_attach
#endif

namespace {

constexpr const char *kSystemPrompt =
    "你是智慧园区低空安防系统的 AI 威胁评估专家。边缘节点会上传多源感知数据\n"
    "（双毫米波雷达、视觉、Remote-ID 身份链、多旋翼特征评分）。\n\n"
    "请评估威胁并严格返回如下 JSON（不要任何额外文字）：\n"
    "{\n"
    "  \"threat_level\": \"LOW|MEDIUM|HIGH|CRITICAL\",\n"
    "  \"assessment\": \"一句话威胁分析（中文，30字内）\",\n"
    "  \"action\": \"处置建议（中文，30字内）\",\n"
    "  \"alert_text\": \"现场告警播报文本（中文，20字内）\",\n"
    "  \"command\": {\n"
    "    \"type\": \"NONE|ADJUST_THRESHOLD|SWITCH_MODE|GENERATE_ALERT|TRIGGER_PARACHUTE\",\n"
    "    \"params\": {}\n"
    "  }\n"
    "}\n\n"
    "判定规则：\n"
    "- 合作目标（RID 白名单通过）→ threat_level=LOW，command.type=NONE\n"
    "- 非合作 + 视觉确认 + 高风险 → threat_level=HIGH/CRITICAL\n"
    "- 多旋翼评分高 + 非合作 → 建议 TRIGGER_PARACHUTE\n"
    "- 若建议 ADJUST_THRESHOLD, 在 params 给 {\"event_threshold\": 数值}(50-90)\n"
    "- 若建议 SWITCH_MODE, 在 params 给 {\"mode\":\"ENHANCED|STANDARD|ECONOMY\", \"reason\":\"理由\"}";

struct ResponseBuffer {
    char *data;
    size_t capacity;
    size_t length;
    bool overflow;
};

void copyText(char *destination, size_t destination_size, const char *source, const char *fallback = "NONE") {
    if (destination == nullptr || destination_size == 0) {
        return;
    }
    const char *value = (source != nullptr && source[0] != '\0') ? source : fallback;
    snprintf(destination, destination_size, "%s", value);
}

void resetResult(CloudAssessmentResult &result, const char *error = "NONE") {
    result = {};
    copyText(result.threat_level, sizeof(result.threat_level), "LOW");
    copyText(result.assessment, sizeof(result.assessment), "云端未返回有效评估");
    copyText(result.action, sizeof(result.action), "保持本地闭环");
    copyText(result.alert_text, sizeof(result.alert_text), "云端评估不可用");
    copyText(result.command_type, sizeof(result.command_type), "NONE");
    result.command_threshold_value = 0.0f;
    copyText(result.command_mode, sizeof(result.command_mode), "STANDARD");
    copyText(result.command_reason, sizeof(result.command_reason), "NONE");
    copyText(result.error, sizeof(result.error), error);
}

cJSON *addObject(cJSON *parent, const char *name) {
    cJSON *child = cJSON_CreateObject();
    if (child == nullptr) {
        return nullptr;
    }
    cJSON_AddItemToObject(parent, name, child);
    return child;
}

bool addString(cJSON *object, const char *name, const char *value) {
    return cJSON_AddStringToObject(object, name, value != nullptr ? value : "NONE") != nullptr;
}

bool addNumber(cJSON *object, const char *name, double value) {
    return cJSON_AddNumberToObject(object, name, value) != nullptr;
}

bool addBool(cJSON *object, const char *name, bool value) {
    return cJSON_AddBoolToObject(object, name, value) != nullptr;
}

bool buildUserEventJson(const CloudSensingEvent &event, char *buffer, size_t buffer_size) {
    if (buffer == nullptr || buffer_size == 0) {
        return false;
    }
    buffer[0] = '\0';

    cJSON *root = cJSON_CreateObject();
    if (root == nullptr) {
        return false;
    }

    bool ok = true;
    ok = ok && addString(root, "event_id", event.event_id);
    ok = ok && addString(root, "target_verdict", event.target_verdict);
    ok = ok && addString(root, "risk_level", event.risk_level);
    ok = ok && addString(root, "fusion_stage", event.fusion_stage);

    cJSON *ld2450 = addObject(root, "ld2450");
    cJSON *ld2451 = addObject(root, "ld2451");
    cJSON *vision = addObject(root, "vision");
    cJSON *rid = addObject(root, "rid");
    cJSON *multirotor = addObject(root, "multirotor");
    ok = ok && ld2450 != nullptr && ld2451 != nullptr && vision != nullptr && rid != nullptr && multirotor != nullptr;

    if (ok) {
        ok = ok && addNumber(ld2450, "x_mm", event.ld2450_x_mm);
        ok = ok && addNumber(ld2450, "y_mm", event.ld2450_y_mm);
        ok = ok && addNumber(ld2450, "vx_mm_s", event.ld2450_vx_mm_s);
        ok = ok && addNumber(ld2450, "vy_mm_s", event.ld2450_vy_mm_s);
        ok = ok && addNumber(ld2451, "range_m", event.ld2451_range_m);
        ok = ok && addNumber(ld2451, "speed_mps", event.ld2451_speed_mps);
        ok = ok && addNumber(vision, "confidence", event.vision_confidence);
        ok = ok && addString(vision, "label", event.vision_label);
        ok = ok && addString(rid, "id", event.rid_id);
        ok = ok && addString(rid, "wl_status", event.wl_status);
        ok = ok && addNumber(multirotor, "score", event.multirotor_score);
        ok = ok && addBool(multirotor, "is_like", event.is_multirotor_like);
    }

    char *printed = ok ? cJSON_PrintUnformatted(root) : nullptr;
    if (printed == nullptr) {
        cJSON_Delete(root);
        return false;
    }

    const bool fits = strlen(printed) < buffer_size;
    if (fits) {
        copyText(buffer, buffer_size, printed, "{}");
    }
    cJSON_free(printed);
    cJSON_Delete(root);
    return fits;
}

esp_err_t httpEventHandler(esp_http_client_event_t *event) {
    if (event == nullptr || event->user_data == nullptr) {
        return ESP_OK;
    }

    ResponseBuffer *response = static_cast<ResponseBuffer *>(event->user_data);
    if (event->event_id == HTTP_EVENT_ON_DATA && event->data != nullptr && event->data_len > 0) {
        const size_t incoming = static_cast<size_t>(event->data_len);
        if (response->length + incoming >= response->capacity) {
            response->overflow = true;
            return ESP_OK;
        }
        memcpy(response->data + response->length, event->data, incoming);
        response->length += incoming;
        response->data[response->length] = '\0';
    }
    return ESP_OK;
}

const char *jsonStringValue(const cJSON *object, const char *name) {
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
    if (cJSON_IsString(item) && item->valuestring != nullptr) {
        return item->valuestring;
    }
    return nullptr;
}

float jsonNumberValue(const cJSON *object, const char *name, float fallback = 0.0f) {
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
    if (cJSON_IsNumber(item)) {
        return static_cast<float>(item->valuedouble);
    }
    return fallback;
}

bool parseAssessmentJson(const char *json, CloudAssessmentResult &result) {
    if (json == nullptr || json[0] == '\0') {
        copyText(result.error, sizeof(result.error), "empty_assessment");
        return false;
    }

    cJSON *root = cJSON_Parse(json);
    if (root == nullptr) {
        copyText(result.error, sizeof(result.error), "assessment_json_parse_failed");
        return false;
    }

    const char *threatLevel = jsonStringValue(root, "threat_level");
    const char *assessment = jsonStringValue(root, "assessment");
    const char *action = jsonStringValue(root, "action");
    const char *alertText = jsonStringValue(root, "alert_text");
    const cJSON *command = cJSON_GetObjectItemCaseSensitive(root, "command");
    const char *commandType = cJSON_IsObject(command) ? jsonStringValue(command, "type") : nullptr;
    const cJSON *params = cJSON_IsObject(command) ? cJSON_GetObjectItemCaseSensitive(command, "params") : nullptr;
    const bool hasParams = cJSON_IsObject(params);
    const char *commandMode = hasParams ? jsonStringValue(params, "mode") : nullptr;
    const char *commandReason = hasParams ? jsonStringValue(params, "reason") : nullptr;

    copyText(result.threat_level, sizeof(result.threat_level), threatLevel, "LOW");
    copyText(result.assessment, sizeof(result.assessment), assessment, "云端评估已返回");
    copyText(result.action, sizeof(result.action), action, "保持本地闭环");
    copyText(result.alert_text, sizeof(result.alert_text), alertText, "云端评估完成");
    copyText(result.command_type, sizeof(result.command_type), commandType, "NONE");
    result.command_threshold_value = hasParams ? jsonNumberValue(params, "event_threshold", 0.0f) : 0.0f;
    copyText(result.command_mode, sizeof(result.command_mode), commandMode, "STANDARD");
    copyText(result.command_reason, sizeof(result.command_reason), commandReason, "NONE");
    copyText(result.error, sizeof(result.error), "NONE");
    cJSON_Delete(root);
    return true;
}

bool parseAssessmentContent(const char *content, CloudAssessmentResult &result) {
    if (content == nullptr || content[0] == '\0') {
        copyText(result.error, sizeof(result.error), "empty_message_content");
        return false;
    }

    if (parseAssessmentJson(content, result)) {
        return true;
    }

    const char *start = strchr(content, '{');
    const char *end = strrchr(content, '}');
    if (start == nullptr || end == nullptr || end <= start) {
        copyText(result.error, sizeof(result.error), "message_content_not_json");
        return false;
    }

    const size_t jsonLength = static_cast<size_t>(end - start + 1);
    if (jsonLength >= 2048) {
        copyText(result.error, sizeof(result.error), "message_content_too_large");
        return false;
    }
    char jsonSlice[2048] = {};
    memcpy(jsonSlice, start, jsonLength);
    jsonSlice[jsonLength] = '\0';
    return parseAssessmentJson(jsonSlice, result);
}

}  // namespace

CloudClient::CloudClient(const char *endpoint, const char *model, const char *api_key)
    : endpoint_(endpoint), model_(model), api_key_(api_key) {}

bool CloudClient::hasCredentials() const {
    return endpoint_ != nullptr && endpoint_[0] != '\0' &&
           model_ != nullptr && model_[0] != '\0' &&
           api_key_ != nullptr && api_key_[0] != '\0';
}

void CloudClient::buildTestEvent(CloudSensingEvent &event) {
    event = {};
    copyText(event.event_id, sizeof(event.event_id), "A1-CLOUD-TEST");
    copyText(event.target_verdict, sizeof(event.target_verdict), "VISUALLY_CONFIRMED_DRONE");
    copyText(event.risk_level, sizeof(event.risk_level), "HIGH_RISK");
    copyText(event.fusion_stage, sizeof(event.fusion_stage), "MID");
    event.ld2450_x_mm = 1234.0f;
    event.ld2450_y_mm = 5678.0f;
    event.ld2450_vx_mm_s = 200.0f;
    event.ld2450_vy_mm_s = -300.0f;
    event.ld2451_range_m = 45.0f;
    event.ld2451_speed_mps = 3.5f;
    event.vision_confidence = 0.82f;
    copyText(event.vision_label, sizeof(event.vision_label), "drone");
    copyText(event.rid_id, sizeof(event.rid_id), "SIM-RID-999");
    copyText(event.wl_status, sizeof(event.wl_status), "WL_DENIED");
    event.multirotor_score = 78.0f;
    event.is_multirotor_like = true;
}

bool CloudClient::buildRequestBody(
    const CloudSensingEvent &event,
    char *buffer,
    size_t buffer_size,
    CloudAssessmentResult &result
) const {
    if (buffer == nullptr || buffer_size == 0) {
        copyText(result.error, sizeof(result.error), "request_buffer_invalid");
        return false;
    }
    buffer[0] = '\0';

    char userContent[1536] = {};
    if (!buildUserEventJson(event, userContent, sizeof(userContent))) {
        copyText(result.error, sizeof(result.error), "event_json_build_failed");
        return false;
    }

    cJSON *root = cJSON_CreateObject();
    cJSON *messages = cJSON_CreateArray();
    cJSON *systemMessage = cJSON_CreateObject();
    cJSON *userMessage = cJSON_CreateObject();
    if (root == nullptr || messages == nullptr || systemMessage == nullptr || userMessage == nullptr) {
        if (root != nullptr) {
            cJSON_Delete(root);
        }
        if (messages != nullptr) {
            cJSON_Delete(messages);
        }
        if (systemMessage != nullptr) {
            cJSON_Delete(systemMessage);
        }
        if (userMessage != nullptr) {
            cJSON_Delete(userMessage);
        }
        copyText(result.error, sizeof(result.error), "request_json_alloc_failed");
        return false;
    }

    cJSON_AddItemToObject(root, "messages", messages);
    cJSON_AddItemToArray(messages, systemMessage);
    cJSON_AddItemToArray(messages, userMessage);
    bool ok = addString(root, "model", model_);
    ok = ok && addString(systemMessage, "role", "system");
    ok = ok && addString(systemMessage, "content", kSystemPrompt);
    ok = ok && addString(userMessage, "role", "user");
    ok = ok && addString(userMessage, "content", userContent);

    char *printed = ok ? cJSON_PrintUnformatted(root) : nullptr;
    if (printed == nullptr) {
        cJSON_Delete(root);
        copyText(result.error, sizeof(result.error), "request_json_print_failed");
        return false;
    }

    const bool fits = strlen(printed) < buffer_size;
    if (fits) {
        copyText(buffer, buffer_size, printed, "{}");
    } else {
        copyText(result.error, sizeof(result.error), "request_json_too_large");
    }
    cJSON_free(printed);
    cJSON_Delete(root);
    return fits;
}

bool CloudClient::parseResponse(const char *response, CloudAssessmentResult &result) const {
    if (response == nullptr || response[0] == '\0') {
        copyText(result.error, sizeof(result.error), "empty_response");
        return false;
    }

    cJSON *root = cJSON_Parse(response);
    if (root == nullptr) {
        copyText(result.error, sizeof(result.error), "response_json_parse_failed");
        return false;
    }

    const cJSON *choices = cJSON_GetObjectItemCaseSensitive(root, "choices");
    const cJSON *firstChoice = cJSON_IsArray(choices) ? cJSON_GetArrayItem(choices, 0) : nullptr;
    const cJSON *message = cJSON_IsObject(firstChoice) ? cJSON_GetObjectItemCaseSensitive(firstChoice, "message") : nullptr;
    const char *content = cJSON_IsObject(message) ? jsonStringValue(message, "content") : nullptr;
    const bool parsed = parseAssessmentContent(content, result);
    cJSON_Delete(root);
    return parsed;
}

bool CloudClient::assess(const CloudSensingEvent &event, CloudAssessmentResult &result) const {
    resetResult(result);
    const unsigned long started = millis();
    if (!hasCredentials()) {
        copyText(result.error, sizeof(result.error), "missing_credentials");
        result.latency_ms = millis() - started;
        return false;
    }

    char requestBody[4096] = {};
    if (!buildRequestBody(event, requestBody, sizeof(requestBody), result)) {
        result.latency_ms = millis() - started;
        return false;
    }

    char responseData[CloudClientLimits::ResponseBufferSize] = {};
    ResponseBuffer response = {responseData, sizeof(responseData), 0, false};
    esp_http_client_config_t config = {};
    config.url = endpoint_;
    config.timeout_ms = CloudClientLimits::HttpTimeoutMs;
    config.crt_bundle_attach = esp_crt_bundle_attach;
    config.event_handler = httpEventHandler;
    config.user_data = &response;

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == nullptr) {
        copyText(result.error, sizeof(result.error), "http_client_init_failed");
        result.latency_ms = millis() - started;
        return false;
    }

    char authorization[160] = {};
    snprintf(authorization, sizeof(authorization), "Bearer %s", api_key_);
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "Authorization", authorization);
    esp_http_client_set_post_field(client, requestBody, static_cast<int>(strlen(requestBody)));

    const esp_err_t err = esp_http_client_perform(client);
    result.esp_error = static_cast<int>(err);
    result.http_status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    result.latency_ms = millis() - started;

    if (err != ESP_OK) {
        copyText(result.error, sizeof(result.error), "http_request_failed");
        return false;
    }
    if (response.overflow) {
        copyText(result.error, sizeof(result.error), "response_too_large");
        return false;
    }
    if (result.http_status < 200 || result.http_status >= 300) {
        copyText(result.error, sizeof(result.error), "http_status_not_ok");
        return false;
    }

    result.parsed = parseResponse(responseData, result);
    result.ok = result.parsed;
    return result.ok;
}
