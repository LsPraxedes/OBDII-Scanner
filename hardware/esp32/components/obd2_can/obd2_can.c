#include "obd2_can.h"
#include "telemetry.h"

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/timers.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_twai.h"
#include "esp_twai_onchip.h"

static const char *TAG = "OBD2_CAN";

// Estrutura de dados para repassar frames da ISR para a task consumidora
typedef struct {
    uint32_t id;
    uint8_t dlc;
    bool ide;
    bool rtr;
    uint8_t data[8];
} can_msg_item_t;

static QueueHandle_t s_rx_queue = NULL;
static twai_node_handle_t s_twai_node = NULL;
static TimerHandle_t s_led_timer = NULL;

// Buffer estático de transmissão OBD-II
static uint8_t s_tx_buffer[8];
static twai_frame_t s_tx_frame = {
    .header = {
        .id = 0x7DF,  // Broadcast padrão OBD-II (11-bit)
        .dlc = 8,
        .ide = false,
        .rtr = false,
    },
    .buffer = s_tx_buffer,
    .buffer_len = sizeof(s_tx_buffer),
};

static void led_timer_callback(TimerHandle_t xTimer) {
    // Apaga o LED de atividade CAN assincronamente após o timer expirar
    gpio_set_level(PIN_CONFIRMA_DADOS, 0);
}

static void setup_confirmation_pins(void) {
    gpio_reset_pin(PIN_CONFIRMA_ENERGIA);
    gpio_set_direction(PIN_CONFIRMA_ENERGIA, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_CONFIRMA_ENERGIA, 0);

    gpio_reset_pin(PIN_CONFIRMA_DADOS);
    gpio_set_direction(PIN_CONFIRMA_DADOS, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_CONFIRMA_DADOS, 0);
}

static void obd2_request_pid(uint8_t pid) {
    if (s_twai_node == NULL) {
        return;
    }

    s_tx_buffer[0] = 0x02; // 2 bytes de dados válidos seguintes (Modo e PID)
    s_tx_buffer[1] = 0x01; // Modo 01: Dados em tempo real
    s_tx_buffer[2] = pid;  // PID solicitado
    s_tx_buffer[3] = 0x55; // Preenchimento padrão ISO 15765-4
    s_tx_buffer[4] = 0x55;
    s_tx_buffer[5] = 0x55;
    s_tx_buffer[6] = 0x55;
    s_tx_buffer[7] = 0x55;

    esp_err_t ret = twai_node_transmit(s_twai_node, &s_tx_frame, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Falha ao enviar requisicao OBD2 para PID 0x%02X (err: %s)",
                 pid, esp_err_to_name(ret));
    }
}

static void twai_transmit_task(void *arg) {
    const uint8_t pids[] = {0x0C, 0x0D, 0x05};
    const char *pid_names[] = {"RPM (0x0C)", "Velocidade (0x0D)", "Temp. Arrefecimento (0x05)"};
    int idx = 0;

    vTaskDelay(pdMS_TO_TICKS(2000));

    while (1) {
        ESP_LOGD(TAG, "--> [OBD2 SOLICITACAO] Enviando requisicao: %s", pid_names[idx]);
        obd2_request_pid(pids[idx]);

        idx = (idx + 1) % 3;
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

static bool twai_rx_cb(twai_node_handle_t handle,
                       const twai_rx_done_event_data_t *edata, void *user_ctx) {
    uint8_t buffer[8];
    twai_frame_t rx_frame = {
        .buffer = buffer,
        .buffer_len = sizeof(buffer),
    };
    BaseType_t high_task_wakeup = pdFALSE;

    if (twai_node_receive_from_isr(handle, &rx_frame) == ESP_OK) {
        can_msg_item_t item;
        memset(&item, 0, sizeof(can_msg_item_t));
        item.id = rx_frame.header.id;
        item.dlc = rx_frame.header.dlc;
        item.ide = rx_frame.header.ide;
        item.rtr = rx_frame.header.rtr;
        for (int i = 0; i < item.dlc && i < 8; i++) {
            item.data[i] = rx_frame.buffer[i];
        }
        xQueueSendFromISR(s_rx_queue, &item, &high_task_wakeup);
    }

    return high_task_wakeup == pdTRUE;
}

static void twai_receive_task(void *arg) {
    can_msg_item_t item;
    while (1) {
        memset(&item, 0, sizeof(can_msg_item_t));
        if (xQueueReceive(s_rx_queue, &item, portMAX_DELAY) == pdTRUE) {
            // Aciona LED de recepção de forma assíncrona
            gpio_set_level(PIN_CONFIRMA_DADOS, 1);
            if (s_led_timer != NULL) {
                xTimerReset(s_led_timer, 0);
            }

            // Decodificação de resposta padrão OBD-II (0x7E8 a 0x7EF)
            if (item.id >= 0x7E8 && item.id <= 0x7EF && item.dlc >= 3 && item.data[1] == 0x41) {
                uint8_t pid = item.data[2];

                if (pid == 0x0C && item.dlc >= 5) { // RPM: ((A * 256) + B) / 4
                    float rpm = (float)((((uint16_t)item.data[3] << 8) | item.data[4]) / 4);
                    ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] RPM DO MOTOR: %.1f RPM", rpm);
                    telemetry_set_rpm(rpm);
                } else if (pid == 0x0D && item.dlc >= 4) { // Velocidade: A km/h
                    float speed = (float)item.data[3];
                    ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] VELOCIDADE: %.1f km/h", speed);
                    telemetry_set_speed(speed);
                } else if (pid == 0x05 && item.dlc >= 4) { // Temperatura: A - 40 °C
                    float temp = (float)((int)item.data[3] - 40);
                    ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] TEMP. MOTOR: %.1f °C", temp);
                    telemetry_set_temperature(temp);
                } else {
                    ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] PID 0x%02X (DLC: %d)", pid, item.dlc);
                }
            } else {
                // Log genérico de outras mensagens do barramento veicular
                if (item.ide) {
                    ESP_LOGD(TAG, "CAN Msg Estendida | ID: 0x%08lX | DLC: %d",
                             (unsigned long)item.id, item.dlc);
                } else {
                    ESP_LOGD(TAG, "CAN Msg Padrao   | ID: 0x%03lX | DLC: %d",
                             (unsigned long)item.id, item.dlc);
                }

                if (!item.rtr && item.dlc > 0) {
                    char hex_str[32] = {0};
                    int offset = 0;
                    for (int i = 0; i < item.dlc && i < 8; i++) {
                        offset += snprintf(hex_str + offset, sizeof(hex_str) - offset,
                                           "%02X ", item.data[i]);
                    }
                    ESP_LOGD(TAG, "Payload HEX: %s", hex_str);
                }
            }
        }
    }
}

esp_err_t obd2_can_init(void) {
    setup_confirmation_pins();

    s_rx_queue = xQueueCreate(20, sizeof(can_msg_item_t));
    if (s_rx_queue == NULL) {
        ESP_LOGE(TAG, "Falha ao alocar fila FreeRTOS para TWAI");
        return ESP_ERR_NO_MEM;
    }

    s_led_timer = xTimerCreate("can_led_timer", pdMS_TO_TICKS(40), pdFALSE, NULL, led_timer_callback);

    xTaskCreate(twai_receive_task, "twai_receive_task", 4096, NULL, 10, NULL);

    twai_onchip_node_config_t node_config = {
        .io_cfg = {
            .tx = CAN_TX_PIN,
            .rx = CAN_RX_PIN,
        },
        .bit_timing = {
            .bitrate = 500000, // 500 kbaud (VW Polo)
        },
        .tx_queue_depth = 5,
    };

    esp_err_t ret = twai_new_node_onchip(&node_config, &s_twai_node);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Falha ao alocar driver TWAI on-chip (%s)", esp_err_to_name(ret));
        return ret;
    }

    twai_event_callbacks_t cbs = {
        .on_rx_done = twai_rx_cb,
    };
    ret = twai_node_register_event_callbacks(s_twai_node, &cbs, NULL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Falha ao registrar callbacks TWAI (%s)", esp_err_to_name(ret));
        return ret;
    }

    ret = twai_node_enable(s_twai_node);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Falha ao habilitar no TWAI (%s)", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "Driver TWAI inicializado com sucesso (500 kbaud)!");
    gpio_set_level(PIN_CONFIRMA_ENERGIA, 1);

    xTaskCreate(twai_transmit_task, "twai_transmit_task", 4096, NULL, 5, NULL);

    return ESP_OK;
}
