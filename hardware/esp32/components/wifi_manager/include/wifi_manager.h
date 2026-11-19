#pragma once

#include "esp_err.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Credenciais da Rede Wi-Fi (Hotspot 4G / Roteador)
#define WIFI_SSID "POCO X7 Pro"
#define WIFI_PASS "umaoitoo"
#define WIFI_MAXIMUM_RETRY 10

// Configuração de Sincronização de Relógio UTC via SNTP
#define WIFI_SNTP_SERVER "pool.ntp.org"
#define WIFI_SNTP_SYNC_TIMEOUT_MS 8000

/**
 * Inicializa NVS, pilha TCP/IP (esp_netif), event loop e conecta ao Wi-Fi em
 * modo Station. Esta função bloqueia a execução até que o ESP32 obtenha um
 * endereço IP com sucesso e realiza a tentativa inicial de sincronização SNTP.
 */
esp_err_t wifi_manager_init_and_wait(void);

/**
 * Verifica se o relógio UTC do sistema já foi sincronizado via SNTP
 * (considera válido quando o ano UTC >= 2025).
 */
bool wifi_manager_is_time_synced(void);

#ifdef __cplusplus
}
#endif
