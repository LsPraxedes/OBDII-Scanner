#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// Pino de Confirmação Visual (LED / Sinal de Envio MQTT)
#define PIN_CONFIRMA_MQTT 26 // Pino D26

#define MQTT_BROKER_URI "mqtts://test.mosquitto.org:8883"
#define MQTT_TOPIC "ls-praxedes/scanner-obd2/qsr5c99"
#define MQTT_PUB_INTERVAL_MS 1000

/**
 * Inicializa o pino D26, cliente MQTTS com TLS v1.2, registra callbacks
 * de eventos e inicia a task FreeRTOS dedicada à publicação periódica da
 * telemetria.
 */
esp_err_t mqtt_service_init(void);

#ifdef __cplusplus
}
#endif
