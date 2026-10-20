# Pull Request #07: Fase 2 (Semana 4) — Firmware Modular em Componentes (CBA), FreeRTOS Mutex e Telemetria MQTTS

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Firmware Embarcado, Arquitetura de Componentes, RTOS e Cibersegurança  
**Commit Associado:** [`c59b8e0f961f34def3af4d769aace8922d498b30`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `c59b8e0`)  
**Data:** 20 de Outubro de 2026 às 09:44:54 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Este marco representa a conclusão dos objetivos da **Semana 4 (Fase 2: Cérebro do Carro)** do cronograma do projeto, consolidando um salto de maturidade no desenvolvimento do software embarcado para o ESP32.

O antigo arquivo monolítico (`main.c`) foi completamente decomposto e reestruturado sob uma **Arquitetura Baseada em Componentes (Component-Based Architecture — CBA)** gerenciada pelo sistema de meta-build **CMake** no ecossistema **ESP-IDF v6.1**. O firmware transformou-se em uma unidade telemática completa: extrai ativamente os PIDs do barramento CAN a 500 kbaud sem atrasos bloqueantes, armazena-os com proteção por **Mutex do FreeRTOS**, conecta-se à rede Wi-Fi Station com recuperação de enlace e transmite dados criptografados via **MQTTS (porta 8883 / TLS v1.2)** com certificado raiz X.509 embutido no binário, sinalizando cada envio no pino **D26 (GPIO 26)**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│             ARQUITETURA MODULAR DE COMPONENTES DO FIRMWARE ESP-IDF (CBA)               │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ hardware/esp32/main/main.c ] (Orquestrador Limpo de 35 Linhas / app_main)
   │
   ├─► 1. [ components/telemetry ]
   │      - Struct de telemetria (RPM, Temp, Speed, Timestamp, Valid Flags)
   │      - Exclusão Mútua Thread-Safe via FreeRTOS Mutex (SemaphoreHandle_t s_mutex)
   │      - Snapshot serializável compatível com schema Pydantic
   │
   ├─► 2. [ components/obd2_can ]
   │      - Driver TWAI nativo configurado a 500 kbaud (Pinos: TX=4, RX=5)
   │      - LEDs de Diagnóstico: D13 (Power On) e D14 (Atividade CAN)
   │      - Eliminação de vTaskDelay! Acionamento do LED via FreeRTOS Software Timer
   │      - Validação defensiva de DLC (>= 3 e >= 5) e escrita atômica em telemetry
   │
   ├─► 3. [ components/wifi_manager ]
   │      - Wi-Fi Station resiliente (SSID "Poco X7 Pro", auto-reconexão contínua)
   │      - Sincronização determinística via EventGroup (WIFI_CONNECTED_BIT)
   │
   └─► 4. [ components/mqtt_service ]
          - Cliente esp-mqtt configurado para "mqtts://test.mosquitto.org:8883"
          - Certificado CA embutido diretamente no binário via EMBED_TXTFILES / ca_cert.h
          - Task periódica (1000 ms): serialização JSON + esp_mqtt_client_publish
          - Confirmação visual no pino D26 / GPIO 26 com desarme por FreeRTOS Software Timer (50 ms)
```

---

## 2. Arquivos Modificados e Criados

| Arquivo / Diretório | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| `hardware/esp32/components/telemetry/` | Criado | +119 / -0 | Componente de telemetria thread-safe com exclusão mútua via FreeRTOS Mutex (`include/telemetry.h`, `telemetry.c`, `CMakeLists.txt`). |
| `hardware/esp32/components/obd2_can/` | Criado | +255 / -0 | Componente CAN/TWAI a 500 kbaud sem bloqueios, temporizador assíncrono para o LED D14 e validação de DLC (`include/obd2_can.h`, `obd2_can.c`, `CMakeLists.txt`). |
| `hardware/esp32/components/wifi_manager/` | Criado | +126 / -0 | Componente Wi-Fi Station com máquina de estados de reconexão e barreira EventGroup (`include/wifi_manager.h`, `wifi_manager.c`, `CMakeLists.txt`). |
| `hardware/esp32/components/mqtt_service/` | Criado | +214 / -0 | Componente MQTTS seguro com TLS v1.2, certificado X.509 embutido, task periódica de despacho JSON e pino D26 (`include/mqtt_service.h`, `include/ca_cert.h`, `mqtt_service.c`, `mosquitto.org.crt`, `CMakeLists.txt`). |
| [hardware/esp32/main/main.c](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/main/main.c) | Modificado | +35 / -272 | Redução do monólito para 35 linhas limpas de orquestração com checagem de erros via `ESP_ERROR_CHECK`. |
| [hardware/esp32/main/CMakeLists.txt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/main/CMakeLists.txt) | Modificado | +5 / -4 | Registro dos novos componentes modulares na cadeia de link-edição. |
| [pytest.ini](file:///c:/Users/lucas/Documents/OBDII%20Scanner/pytest.ini) | Modificado | +1 / -0 | Ajuste de configuração de execução de testes. |
| [backend/tests/test_mqtt.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_mqtt.py) | Modificado | +0 / -1 | Limpeza de comentário e alinhamento de schema. |

---

## 3. Detalhamento Técnico dos Componentes Criados

### 3.1. Componente `telemetry` (`components/telemetry/`)
* **Papel:** Repositório central de dados em tempo real da dinâmica veicular.
* **Estrutura de Dados:**
  ```c
  typedef struct {
      float rpm;
      float temperature;
      float speed;
      int64_t timestamp_ms;
      bool rpm_valid;
      bool temp_valid;
      bool speed_valid;
  } telemetry_data_t;
  ```
* **Thread-Safety e Exclusão Mútua:**  
  Protegido internamente por um semáforo de exclusão mútua (`SemaphoreHandle_t s_mutex`). Funções de escrita (`telemetry_set_rpm`, etc.) e leitura de cópia segura (`telemetry_get_snapshot`) exigem a posse do mutex com timeout controlado (`pdMS_TO_TICKS(100)`), garantindo que leituras pela task MQTT nunca capturem memória corrompida durante a atualização atômica da task CAN.

### 3.2. Componente `obd2_can` (`components/obd2_can/`)
* **Eliminação de Gargalo de Fila (Zero Blocking Delay):**  
  O antigo atraso bloqueante de 40 ms foi inteiramente extirpado da tarefa de recepção de frames. O controle luminoso do LED D14 foi transferido para um temporizador de software assíncrono do FreeRTOS (`can_led_timer` de 30 ms). A task de recepção apenas liga o LED e arma o timer assíncrono, retornando imediatamente ao escalonador para drenar a fila `s_rx_queue` do driver TWAI sem perder frames em rajadas veiculares.
* **Validação Defensiva de DLC (ISO 15765-4):**  
  Antes de acessar os bytes de carga útil, o código confere `item.dlc >= 3` (para temperatura e velocidade) e `item.dlc >= 5` (para RPM), prevenindo falhas de segmentação de memória em caso de pacotes ruidosos.

### 3.3. Componente `wifi_manager` (`components/wifi_manager/`)
* **Resiliência e Tolerância a Quedas:**  
  Tratamento de eventos `WIFI_EVENT_STA_DISCONNECTED` com máquina de estados de reconexão automática e backoff, garantindo reconexão transparente ao hotspot veicular 4G.
* **Barreira de Sincronização via EventGroup:**  
  Utiliza `EventGroupHandle_t` com a flag `WIFI_CONNECTED_BIT`. A função `wifi_manager_init_and_wait()` bloqueia ordenadamente a thread de boot até que o evento `IP_EVENT_STA_GOT_IP` confirme a concessão de endereço IP válido pelo servidor DHCP.

### 3.4. Componente `mqtt_service` (`components/mqtt_service/`)
* **Pilha MQTTS Segura com Certificado Embutido:**  
  Configura o cliente `esp-mqtt` com a URI `mqtts://test.mosquitto.org:8883`. O certificado CA `mosquitto.org.crt` é convertido diretamente em símbolos de link-edição através da instrução `EMBED_TXTFILES` no `CMakeLists.txt`, eliminando a necessidade de ler arquivos em cartões SD ou partições SPIFFS externas.
* **Task Periódica de Serialização e Publicação:**  
  A task `mqtt_publisher_task` acorda a cada 1000 ms. Ao constatar conexão ativa com o broker e presença de dados no snapshot de telemetria, gera um payload JSON rigorosamente compatível com o schema Pydantic do backend:
  ```json
  {"rpm": 2500.0, "temperature": 90.0, "speed": 80.0}
  ```
* **Sinalização Visual em Hardware (Pino D26 / GPIO 26):**  
  A cada publicação confirmada via `esp_mqtt_client_publish`, o pino D26 é levado a nível alto (`1`), disparando um temporizador de software FreeRTOS de 50 ms (`mqtt_led_timer`) para desarmar o LED de forma 100% não-bloqueante.

### 3.5. Orquestrador Principal (`main/main.c`)
Reduzido a um fluxo sequencial, limpo e à prova de falhas:
```c
void app_main(void) {
    ESP_LOGI(TAG, "Central de Analise Veicular Preditiva (IoT) - ESP32 Firmware");
    ESP_ERROR_CHECK(telemetry_init());
    ESP_ERROR_CHECK(obd2_can_init());
    ESP_ERROR_CHECK(wifi_manager_init_and_wait());
    ESP_ERROR_CHECK(mqtt_service_init());
}
```

---

## 4. Avaliação Comparativa: Monólito vs. Arquitetura em Componentes (CBA)

| Critério Técnico | Abordagem Anterior (PR #05) | Arquitetura Modular (PR #07) |
| :--- | :--- | :--- |
| **Linhas de Código em `main.c`** | 272 linhas misturando drivers, rede e lógica | 35 linhas limpas de orquestração sequencial |
| **Concorrência e Acesso a Dados** | Variáveis globais expostas com risco de *race condition* | Repositório `telemetry` protegido por Mutex do FreeRTOS |
| **Gargalo no Barramento CAN** | Delay bloqueante de 40 ms na task de recepção (risco de overflow) | Timer assíncrono FreeRTOS de 30 ms; sem atrasos na recepção |
| **Conectividade de Rede** | Inexistente no firmware ESP-IDF | Wi-Fi Station resiliente com EventGroup de sincronização |
| **Segurança Telemática** | Nenhuma | MQTTS (TLS v1.2 / porta 8883) com certificado X.509 embutido |
| **Confirmação Visual em Campo** | Apenas LEDs de Power (D13) e CAN (D14) | Confirmação de pacote transmitido via MQTTS no LED **D26** |
| **Sistema de Build** | Componente único contendo todo o código | 4 componentes isolados gerenciados via meta-build CMake |

---

## 5. Mapeamento Geral de Pinos de Hardware (Pinout)

| GPIO | Identificação DevKit | Direção | Função no Sistema | Módulo Responsável |
| :---: | :---: | :---: | :--- | :--- |
| **GPIO 4** | D4 | Saída (TX) | Linha de Transmissão CAN para Transceptor SN65HVD230 | `obd2_can` |
| **GPIO 5** | D5 | Entrada (RX) | Linha de Recepção CAN do Transceptor SN65HVD230 | `obd2_can` |
| **GPIO 13** | D13 | Saída Digital | LED Indicador de Sistema Ativo / Alimentação TWAI | `obd2_can` |
| **GPIO 14** | D14 | Saída Digital | LED Indicador de Pacote CAN Recebido da ECU do Veículo | `obd2_can` |
| **GPIO 26** | D26 | Saída Digital | LED Indicador de Pacote Telemático Enviado via MQTTS | `mqtt_service` |

---

## 6. Plano de Validação e Testes

1. **Compilação e Link-Edição:** Compilação com `idf.py build` concluída sem alertas nem erros de símbolos pendentes.
2. **Conformidade de Schema:** Validação com a suíte de testes automatizados do backend (`python -m pytest`): 6 testes passando com êxito.
3. **Comunicação Segura de Ponta a Ponta:** Verificação da recepção no broker Mosquitto através de subscrição TLS em `ls-praxedes/scanner-obd2/+` na porta 8883.
