#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// Credenciais da Rede Wi-Fi (Hotspot 4G / Roteador)
#define WIFI_SSID           "Poco X7 Pro"
#define WIFI_PASS           "umaoitoo"
#define WIFI_MAXIMUM_RETRY  10

/**
 * Inicializa NVS, pilha TCP/IP (esp_netif), event loop e conecta ao Wi-Fi em modo Station.
 * Esta função bloqueia a execução até que o ESP32 obtenha um endereço IP com sucesso.
 */
esp_err_t wifi_manager_init_and_wait(void);

#ifdef __cplusplus
}
#endif
