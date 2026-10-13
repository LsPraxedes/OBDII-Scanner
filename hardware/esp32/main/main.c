#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_twai.h"
#include "esp_twai_onchip.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <stdio.h>
#include <stdlib.h>

// Pinos do Transceptor CAN/TWAI (ESP32 WROOM-32 DevKit V1)
// Nota: NUNCA use GPIO 1/3 (UART0/USB) nem GPIO 6-11 (Flash SPI interna)
#define TX_PIN 4
#define RX_PIN 5

// Pinos de Confirmação Visual (LEDs)
// Nota: No WROOM-32, pinos 34-39 são Input Only e 37 não existe no header.
// Usamos GPIOs de uso geral com suporte a saída (OUTPUT):
#define PIN_CONFIRMA_ENERGIA 13
#define PIN_CONFIRMA_DADOS 14

static const char *TAG = "OBD2_SCANNER";

// Estrutura para repassar os dados recebidos da ISR para a task de
// processamento
typedef struct {
  uint32_t id;
  uint8_t dlc;
  bool ide;
  bool rtr;
  uint8_t data[8];
} can_msg_item_t;

static QueueHandle_t s_rx_queue = NULL;
static twai_node_handle_t s_twai_node = NULL;

/**
 * Buffer estático para envio (deve permanecer válido na memória para o driver
 * TWAI)
 */
static uint8_t s_tx_buffer[8];
static twai_frame_t s_tx_frame = {
    .header =
        {
            .id =
                0x7DF, // ID padrão de Broadcast de Diagnóstico OBD-II (11-bit)
            .dlc = 8,
            .ide = false, // ID padrão (11 bits)
            .rtr = false,
        },
    .buffer = s_tx_buffer,
    .buffer_len = sizeof(s_tx_buffer),
};

/**
 * Envia uma requisição padrão OBD-II (Modo 01) para um PID específico.
 */
void obd2_request_pid(uint8_t pid) {
  if (s_twai_node == NULL) {
    return;
  }

  s_tx_buffer[0] = 0x02; // Quantidade de bytes de comando a seguir
  s_tx_buffer[1] = 0x01; // Modo 01: Dados em tempo real (Current Data)
  s_tx_buffer[2] = pid;  // PID solicitado
  s_tx_buffer[3] = 0x55; // Preenchimento padrão ISO 15765-4
  s_tx_buffer[4] = 0x55;
  s_tx_buffer[5] = 0x55;
  s_tx_buffer[6] = 0x55;
  s_tx_buffer[7] = 0x55;

  esp_err_t ret =
      twai_node_transmit(s_twai_node, &s_tx_frame, pdMS_TO_TICKS(100));
  if (ret != ESP_OK) {
    ESP_LOGW(TAG, "Falha ao enviar requisicao OBD2 para PID 0x%02X (err: %s)",
             pid, esp_err_to_name(ret));
  }
}

/**
 * Task FreeRTOS dedicada a solicitar ciclicamente os PIDs da ECU do veículo.
 */
void twai_transmit_task(void *arg) {
  const uint8_t pids[] = {
      0x0C, 0x0D, 0x05}; // 0x0C: RPM | 0x0D: Velocidade | 0x05: Temp Motor
  const char *pid_names[] = {"RPM (0x0C)", "Velocidade (0x0D)",
                             "Temp. Arrefecimento (0x05)"};
  int idx = 0;

  // Aguarda 2 segundos para o barramento se estabilizar
  vTaskDelay(pdMS_TO_TICKS(2000));

  while (1) {
    ESP_LOGI(TAG, "--> [OBD2 SOLICITACAO] Enviando requisicao para: %s",
             pid_names[idx]);
    obd2_request_pid(pids[idx]);

    idx = (idx + 1) % 3;
    vTaskDelay(pdMS_TO_TICKS(500)); // Envia uma requisição a cada 500 ms
  }
}

/**
 * Callback executado no contexto de interrupção (ISR) assim que uma mensagem
 * CAN chega no hardware.
 */
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

/**
 * Configuração dos pinos dos LEDs de confirmação visual.
 */
void setup_confirmation_pins(void) {
  // Configura o pino de confirmação de energia (LED Power / Sistema Pronto)
  gpio_reset_pin(PIN_CONFIRMA_ENERGIA);
  gpio_set_direction(PIN_CONFIRMA_ENERGIA, GPIO_MODE_OUTPUT);
  gpio_set_level(PIN_CONFIRMA_ENERGIA, 0);

  // Configura o pino de dados da ECU (LED Atividade de Tráfego CAN)
  gpio_reset_pin(PIN_CONFIRMA_DADOS);
  gpio_set_direction(PIN_CONFIRMA_DADOS, GPIO_MODE_OUTPUT);
  gpio_set_level(PIN_CONFIRMA_DADOS, 0);
}

/**
 * Task FreeRTOS dedicada a processar as mensagens retiradas da fila e emitir
 * logs.
 */
void twai_receive_task(void *arg) {
  can_msg_item_t item;
  while (1) {
    if (xQueueReceive(s_rx_queue, &item, portMAX_DELAY) == pdTRUE) {
      // Aciona o LED de recepção de dados da ECU
      gpio_set_level(PIN_CONFIRMA_DADOS, 1);

      // 1. Decodificação Especial: Resposta Padrão OBD-II da ECU (Faixa 0x7E8 a
      // 0x7EF)
      if (item.id >= 0x7E8 && item.id <= 0x7EF && item.data[1] == 0x41) {
        uint8_t pid = item.data[2];

        if (pid == 0x0C) { // RPM do Motor: ((A * 256) + B) / 4
          uint16_t rpm = (((uint16_t)item.data[3] << 8) | item.data[4]) / 4;
          ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] RPM DO MOTOR: %u RPM", rpm);
        } else if (pid == 0x0D) { // Velocidade: A km/h
          uint8_t speed = item.data[3];
          ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] VELOCIDADE: %u km/h",
                   speed);
        } else if (pid ==
                   0x05) { // Temperatura do Líquido de Arrefecimento: A - 40 °C
          int temp = (int)item.data[3] - 40;
          ESP_LOGI(TAG, "=====> [OBD2 RESPOSTA ECU] TEMP. MOTOR: %d °C", temp);
        } else {
          ESP_LOGI(TAG,
                   "=====> [OBD2 RESPOSTA ECU] PID 0x%02X: [0x%02X 0x%02X]",
                   pid, item.data[3], item.data[4]);
        }
      } else {
        // 2. Log Genérico de Tráfego do Barramento
        if (item.ide) {
          ESP_LOGI(TAG, "Mensagem Estendida Recebida | ID: 0x%08lX | DLC: %d",
                   (unsigned long)item.id, item.dlc);
        } else {
          ESP_LOGI(TAG, "Mensagem Padrao Recebida   | ID: 0x%03lX | DLC: %d",
                   (unsigned long)item.id, item.dlc);
        }

        if (!item.rtr && item.dlc > 0) {
          char hex_str[32] = {0};
          int offset = 0;
          for (int i = 0; i < item.dlc && i < 8; i++) {
            offset += snprintf(hex_str + offset, sizeof(hex_str) - offset,
                               "%02X ", item.data[i]);
          }
          ESP_LOGI(TAG, "Payload HEX: %s", hex_str);
        }
      }

      // Delay perceptível para o olho humano e desliga o LED
      vTaskDelay(pdMS_TO_TICKS(40));
      gpio_set_level(PIN_CONFIRMA_DADOS, 0);
    }
  }
}

void app_main(void) {
  ESP_LOGI(TAG, "Iniciando Central de Analise Veicular Preditiva (IoT) - Fase "
                "2 (Leitura Ativa OBD-II)");

  // Configura os LEDs de saída
  setup_confirmation_pins();

  // Cria a fila para tráfego seguro de mensagens entre a ISR e a Task
  s_rx_queue = xQueueCreate(20, sizeof(can_msg_item_t));
  if (s_rx_queue == NULL) {
    ESP_LOGE(TAG, "Falha ao alocar fila FreeRTOS");
    return;
  }

  // Cria a task consumidora/decodificadora
  xTaskCreate(twai_receive_task, "twai_receive_task", 4096, NULL, 10, NULL);

  // Configuração oficial do novo driver TWAI On-Chip (500 kbaud para o VW Polo)
  twai_onchip_node_config_t node_config = {
      .io_cfg =
          {
              .tx = TX_PIN,
              .rx = RX_PIN,
          },
      .bit_timing =
          {
              .bitrate = 500000,
          },
      .tx_queue_depth = 5,
  };

  if (twai_new_node_onchip(&node_config, &s_twai_node) != ESP_OK) {
    ESP_LOGE(TAG, "Falha ao alocar o driver TWAI on-chip");
    return;
  }

  // Registra a função de callback de recepção via interrupção (ISR)
  twai_event_callbacks_t cbs = {
      .on_rx_done = twai_rx_cb,
  };
  if (twai_node_register_event_callbacks(s_twai_node, &cbs, NULL) != ESP_OK) {
    ESP_LOGE(TAG, "Falha ao registrar callback de recepção");
    return;
  }

  // Habilita o nó no barramento CAN
  if (twai_node_enable(s_twai_node) != ESP_OK) {
    ESP_LOGE(TAG, "Falha ao habilitar nó TWAI");
    return;
  }

  ESP_LOGI(TAG, "Driver TWAI (Nova API) inicializado e escutando a 500 kbaud!");

  // Acende LED de energia confirmando que o sistema está pronto
  gpio_set_level(PIN_CONFIRMA_ENERGIA, 1);

  // Cria a task que envia as perguntas periódicas para a ECU (0x7DF)
  xTaskCreate(twai_transmit_task, "twai_transmit_task", 4096, NULL, 5, NULL);
}
