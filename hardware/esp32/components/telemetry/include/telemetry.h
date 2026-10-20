#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Estrutura de Telemetria Compartilhada (Padrão Schema Pydantic do Backend)
 */
typedef struct {
    float rpm;
    float speed;
    float temperature;
    bool has_rpm;
    bool has_speed;
    bool has_temperature;
    uint32_t last_update_ms;
} vehicle_telemetry_t;

/**
 * Inicializa os recursos de sincronização (Mutex) da telemetria.
 */
esp_err_t telemetry_init(void);

/**
 * Atualiza o valor de RPM de forma thread-safe.
 */
void telemetry_set_rpm(float rpm);

/**
 * Atualiza o valor de Velocidade de forma thread-safe.
 */
void telemetry_set_speed(float speed);

/**
 * Atualiza o valor de Temperatura de forma thread-safe.
 */
void telemetry_set_temperature(float temp);

/**
 * Obtém uma cópia instantânea (snapshot) segura dos dados de telemetria.
 * Retorna true se os dados obrigatórios mínimos (RPM e Temperatura) já foram lidos.
 */
bool telemetry_get_snapshot(vehicle_telemetry_t *out_data);

#ifdef __cplusplus
}
#endif
