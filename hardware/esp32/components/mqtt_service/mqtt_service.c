#include "mqtt_service.h"
#include "ca_cert.h"
#include "telemetry.h"
#include "wifi_manager.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/timers.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "mqtt_client.h"

static const char *TAG = "MQTT_SVC";

static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static bool s_mqtt_connected = false;
static TimerHandle_t s_mqtt_led_timer = NULL;

static bool format_current_utc_iso8601(char *out_buf, size_t out_len) {
  if (out_buf == NULL || out_len < 25 || !wifi_manager_is_time_synced()) {
    return false;
  }

  struct timeval tv = {0};
  struct tm tm_utc = {0};
  if (gettimeofday(&tv, NULL) != 0) {
    return false;
  }

  gmtime_r(&tv.tv_sec, &tm_utc);
  if (tm_utc.tm_year < (2025 - 1900)) {
    return false;
  }

  int millis = (int)(tv.tv_usec / 1000);
  if (millis < 0) {
    millis = 0;
  } else if (millis > 999) {
    millis = 999;
  }

  int written =
      snprintf(out_buf, out_len, "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
               tm_utc.tm_year + 1900, tm_utc.tm_mon + 1, tm_utc.tm_mday,
               tm_utc.tm_hour, tm_utc.tm_min, tm_utc.tm_sec, millis);
  return (written > 0 && (size_t)written < out_len);
}

static void mqtt_led_timer_callback(TimerHandle_t xTimer) {
  // Desliga o pino D26 assincronamente após o envio
  gpio_set_level(PIN_CONFIRMA_MQTT, 0);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base,
                               int32_t event_id, void *event_data) {
  esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
  switch ((esp_mqtt_event_id_t)event_id) {
  case MQTT_EVENT_CONNECTED:
    ESP_LOGI(TAG, "MQTTS: Conectado com sucesso ao broker %s!",
             MQTT_BROKER_URI);
    s_mqtt_connected = true;
    break;
  case MQTT_EVENT_DISCONNECTED:
    ESP_LOGW(TAG, "MQTTS: Conexao com broker encerrada.");
    s_mqtt_connected = false;
    break;
  case MQTT_EVENT_ERROR:
    ESP_LOGE(TAG, "MQTTS: Erro na camada MQTT/TLS (tipo=%d)",
             event->error_handle ? event->error_handle->error_type : -1);
    break;
  default:
    break;
  }
}

static void mqtt_publisher_task(void *arg) {
  char payload[192];
  char iso_timestamp[32];

  while (1) {
    vTaskDelay(pdMS_TO_TICKS(MQTT_PUB_INTERVAL_MS));

    if (!s_mqtt_connected) {
      continue;
    }

    vehicle_telemetry_t data;
    if (telemetry_get_snapshot(&data)) {
      bool has_valid_time =
          format_current_utc_iso8601(iso_timestamp, sizeof(iso_timestamp));

      if (has_valid_time) {
        if (data.has_speed) {
          snprintf(payload, sizeof(payload),
                   "{\"rpm\": %.1f, \"temperature\": %.1f, \"speed\": %.1f, "
                   "\"timestamp\": \"%s\"}",
                   data.rpm, data.temperature, data.speed, iso_timestamp);
        } else {
          snprintf(
              payload, sizeof(payload),
              "{\"rpm\": %.1f, \"temperature\": %.1f, \"timestamp\": \"%s\"}",
              data.rpm, data.temperature, iso_timestamp);
        }
      } else {
        if (data.has_speed) {
          snprintf(payload, sizeof(payload),
                   "{\"rpm\": %.1f, \"temperature\": %.1f, \"speed\": %.1f}",
                   data.rpm, data.temperature, data.speed);
        } else {
          snprintf(payload, sizeof(payload),
                   "{\"rpm\": %.1f, \"temperature\": %.1f}", data.rpm,
                   data.temperature);
        }
      }

      int msg_id =
          esp_mqtt_client_publish(s_mqtt_client, MQTT_TOPIC, payload, 0, 1, 0);
      if (msg_id >= 0) {
        // Aciona o pino D26 confirmando visualmente o envio do pacote MQTT
        gpio_set_level(PIN_CONFIRMA_MQTT, 1);
        if (s_mqtt_led_timer != NULL) {
          xTimerReset(s_mqtt_led_timer, 0);
        }

        ESP_LOGI(TAG,
                 "--> [MQTT PUBLICADO] Topico: %s | MsgID: %d | Payload: %s",
                 MQTT_TOPIC, msg_id, payload);
      } else {
        ESP_LOGW(TAG, "Falha ao publicar telemetria no broker (ret: %d)",
                 msg_id);
      }
    } else {
      ESP_LOGD(TAG,
               "Aguardando leitura completa dos dados da ECU para publicar...");
    }
  }
}

esp_err_t mqtt_service_init(void) {
  // 1. Configuração do pino D26 para confirmação visual de envio MQTT
  gpio_reset_pin(PIN_CONFIRMA_MQTT);
  gpio_set_direction(PIN_CONFIRMA_MQTT, GPIO_MODE_OUTPUT);
  gpio_set_level(PIN_CONFIRMA_MQTT, 0);

  // Timer assíncrono (50ms) para desligar o LED D26 sem bloquear a task
  s_mqtt_led_timer = xTimerCreate("mqtt_led_timer", pdMS_TO_TICKS(50), pdFALSE,
                                  NULL, mqtt_led_timer_callback);

  // 2. Configuração do cliente MQTTS com certificado TLS
  esp_mqtt_client_config_t mqtt_cfg = {
      .broker =
          {
              .address =
                  {
                      .uri = MQTT_BROKER_URI,
                  },
              .verification =
                  {
                      .certificate = mosquitto_ca_cert,
                  },
          },
  };

  s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
  if (s_mqtt_client == NULL) {
    ESP_LOGE(TAG, "Falha ao alocar cliente MQTT");
    return ESP_FAIL;
  }

  esp_err_t ret = esp_mqtt_client_register_event(
      s_mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Falha ao registrar eventos MQTT (%s)", esp_err_to_name(ret));
    return ret;
  }

  ret = esp_mqtt_client_start(s_mqtt_client);
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Falha ao iniciar cliente MQTT (%s)", esp_err_to_name(ret));
    return ret;
  }

  xTaskCreate(mqtt_publisher_task, "mqtt_publisher_task", 4096, NULL, 5, NULL);

  return ESP_OK;
}
