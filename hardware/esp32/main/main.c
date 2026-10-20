#include "esp_log.h"
#include "esp_err.h"

#include "telemetry.h"
#include "obd2_can.h"
#include "wifi_manager.h"
#include "mqtt_service.h"

static const char *TAG = "APP_MAIN";

/**
 * Ponto de Entrada Principal (Orquestrador do Firmware)
 * Inicializa cada subsistema em sequência modular e segura.
 */
void app_main(void) {
    ESP_LOGI(TAG, "==========================================================");
    ESP_LOGI(TAG, "Central de Analise Veicular Preditiva (IoT) - ESP32 Firmware");
    ESP_LOGI(TAG, "Arquitetura Modular: CAN/TWAI + FreeRTOS + Wi-Fi + MQTTS");
    ESP_LOGI(TAG, "==========================================================");

    // 1. Inicializa o repositório de telemetria compartilhado (Mutex/Snapshot)
    ESP_ERROR_CHECK(telemetry_init());

    // 2. Inicializa o barramento CAN / TWAI (500 kbaud) e pinos de confirmação visual (D13 Power, D14 CAN)
    ESP_ERROR_CHECK(obd2_can_init());

    // 3. Inicializa o Wi-Fi em modo Station e aguarda a obtenção de IP
    ESP_ERROR_CHECK(wifi_manager_init_and_wait());

    // 4. Inicializa o cliente MQTTS (TLS 8883) com feedback no pino D26 e task de publicação
    ESP_ERROR_CHECK(mqtt_service_init());

    ESP_LOGI(TAG, "Todos os modulos foram inicializados com sucesso! Sistema em operacao.");
}
