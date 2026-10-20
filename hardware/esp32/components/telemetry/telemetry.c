#include "telemetry.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"

static const char *TAG = "TELEMETRY";
static vehicle_telemetry_t s_telemetry = {0};
static SemaphoreHandle_t s_mutex = NULL;

esp_err_t telemetry_init(void) {
    if (s_mutex == NULL) {
        s_mutex = xSemaphoreCreateMutex();
        if (s_mutex == NULL) {
            ESP_LOGE(TAG, "Falha ao alocar Mutex da telemetria");
            return ESP_ERR_NO_MEM;
        }
    }
    memset(&s_telemetry, 0, sizeof(vehicle_telemetry_t));
    ESP_LOGI(TAG, "Modulo de telemetria inicializado com sucesso.");
    return ESP_OK;
}

void telemetry_set_rpm(float rpm) {
    if (s_mutex != NULL && xSemaphoreTake(s_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        s_telemetry.rpm = rpm;
        s_telemetry.has_rpm = true;
        s_telemetry.last_update_ms = (uint32_t)esp_log_timestamp();
        xSemaphoreGive(s_mutex);
    }
}

void telemetry_set_speed(float speed) {
    if (s_mutex != NULL && xSemaphoreTake(s_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        s_telemetry.speed = speed;
        s_telemetry.has_speed = true;
        s_telemetry.last_update_ms = (uint32_t)esp_log_timestamp();
        xSemaphoreGive(s_mutex);
    }
}

void telemetry_set_temperature(float temp) {
    if (s_mutex != NULL && xSemaphoreTake(s_mutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        s_telemetry.temperature = temp;
        s_telemetry.has_temperature = true;
        s_telemetry.last_update_ms = (uint32_t)esp_log_timestamp();
        xSemaphoreGive(s_mutex);
    }
}

bool telemetry_get_snapshot(vehicle_telemetry_t *out_data) {
    if (out_data == NULL || s_mutex == NULL) {
        return false;
    }

    bool is_valid = false;
    if (xSemaphoreTake(s_mutex, pdMS_TO_TICKS(50)) == pdTRUE) {
        *out_data = s_telemetry;
        // Valida se os campos obrigatórios pelo backend (RPM e Temp) já foram preenchidos
        is_valid = s_telemetry.has_rpm && s_telemetry.has_temperature;
        xSemaphoreGive(s_mutex);
    }
    return is_valid;
}
