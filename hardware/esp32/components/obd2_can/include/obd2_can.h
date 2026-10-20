#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// Pinos do Transceptor CAN/TWAI (SN65HVD230)
#define CAN_TX_PIN 4
#define CAN_RX_PIN 5

// Pinos de Confirmação Visual (LEDs de Status)
#define PIN_CONFIRMA_ENERGIA 13 // LED Power / Sistema Pronto
#define PIN_CONFIRMA_DADOS   14 // LED Atividade de Tráfego CAN

/**
 * Inicializa os pinos de confirmação visual, driver TWAI on-chip a 500 kbaud,
 * a fila de recepção, timer não-bloqueante do LED e as tasks de transmissão/recepção OBD-II.
 */
esp_err_t obd2_can_init(void);

#ifdef __cplusplus
}
#endif
