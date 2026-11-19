#include "wifi_manager.h"

#include <time.h>
#include <sys/time.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "nvs_flash.h"

static const char *TAG = "WIFI_MGR";

static EventGroupHandle_t s_wifi_event_group = NULL;
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

static int s_retry_num = 0;
static bool s_sntp_initialized = false;

bool wifi_manager_is_time_synced(void) {
    time_t now = 0;
    struct tm tm_utc = {0};
    time(&now);
    gmtime_r(&now, &tm_utc);
    return (tm_utc.tm_year >= (2025 - 1900));
}

static void wifi_manager_init_sntp(void) {
    if (!s_sntp_initialized) {
        ESP_LOGI(TAG, "Inicializando cliente SNTP (servidor: %s)...", WIFI_SNTP_SERVER);
        esp_sntp_config_t sntp_cfg = ESP_NETIF_SNTP_DEFAULT_CONFIG(WIFI_SNTP_SERVER);
        esp_err_t sntp_ret = esp_netif_sntp_init(&sntp_cfg);
        if (sntp_ret != ESP_OK) {
            ESP_LOGW(TAG, "Falha ao inicializar SNTP (%s). Prosseguindo sem timestamp de origem.",
                     esp_err_to_name(sntp_ret));
            return;
        }
        s_sntp_initialized = true;
    }

    esp_err_t sync_ret = esp_netif_sntp_sync_wait(pdMS_TO_TICKS(WIFI_SNTP_SYNC_TIMEOUT_MS));
    if (sync_ret == ESP_OK && wifi_manager_is_time_synced()) {
        time_t now = 0;
        struct tm tm_utc = {0};
        char time_buf[32];
        time(&now);
        gmtime_r(&now, &tm_utc);
        strftime(time_buf, sizeof(time_buf), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);
        ESP_LOGI(TAG, "Relogio UTC sincronizado via SNTP: %s", time_buf);
    } else {
        ESP_LOGW(TAG, "Timeout (%d ms) aguardando sincronizacao SNTP. O cliente continuara tentando em background.",
                 WIFI_SNTP_SYNC_TIMEOUT_MS);
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "Wi-Fi Station iniciado. Conectando ao SSID '%s'...", WIFI_SSID);
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
        if (s_retry_num < WIFI_MAXIMUM_RETRY) {
            s_retry_num++;
            ESP_LOGW(TAG, "Reconectando ao Wi-Fi (tentativa %d/%d)...",
                     s_retry_num, WIFI_MAXIMUM_RETRY);
            esp_wifi_connect();
        } else {
            ESP_LOGE(TAG, "Limite de tentativas Wi-Fi atingido. Nova tentativa em 5 segundos...");
            vTaskDelay(pdMS_TO_TICKS(5000));
            esp_wifi_connect();
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Wi-Fi Conectado com sucesso! Endereco IP obtido: " IPSTR,
                 IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

esp_err_t wifi_manager_init_and_wait(void) {
    // 1. Inicializa a memória não-volátil (NVS)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Falha ao inicializar NVS Flash (%s)", esp_err_to_name(ret));
        return ret;
    }

    s_wifi_event_group = xEventGroupCreate();
    if (s_wifi_event_group == NULL) {
        ESP_LOGE(TAG, "Falha ao criar EventGroup do Wi-Fi");
        return ESP_ERR_NO_MEM;
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Aguardando sincronizacao de conexao Wi-Fi...");
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT, pdFALSE, pdFALSE, portMAX_DELAY);

    // 2. Inicializa e aguarda sincronizacao inicial do relogio UTC via SNTP
    wifi_manager_init_sntp();

    return ESP_OK;
}
