# Pull Request #05: Fase 2 (Semana 3) — Firmware C Nativo no ESP-IDF e Leitura Ativa OBD-II no Barramento CAN/TWAI

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Firmware Embarcado, Barramento CAN/TWAI e Diagnóstico Automotivo  
**Commit Associado:** [`c08422743ae6516ac99acfabdd006af9bd5bed9e`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `c084227`)  
**Data:** 13 de Outubro de 2026 às 15:22:30 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Este marco representa a entrega dos objetivos da **Semana 3**, iniciando formalmente a **Fase 2 (Hardware Embarcado em C / ESP-IDF)** do projeto. A plataforma Arduino foi definitivamente abandonada em prol do framework profissional da Espressif, o **ESP-IDF v6.1**, programado em **Linguagem C**.

O foco técnico desta entrega concentrou-se na camada física e de enlace do veículo: configuração do periférico de hardware nativo **TWAI (Two-Wire Automotive Interface)** do chip ESP32 para operar como nó de barramento CAN a **500 kbaud** (padrão de fábrica do Volkswagen Polo Track), interligado ao transceptor de linha **SN65HVD230**. O firmware implementou o mecanismo de requisição ativa (*query/response*) segundo o padrão automotivo internacional **ISO 15765-4 / SAE J1979**, transmitindo broadcasts para o identificador padrão da ECU (`0x7DF`) no Modo `0x01` e decodificando as respostas emitidas pelo módulo de injeção eletrônica ECM (`0x7E8`).

```
┌────────────────────────────────────────────────────────────────────────┐
│          COMUNICAÇÃO OBD-II NO BARRAMENTO CAN (SEMANA 3 - TWAI)       │
└────────────────────────────────────────────────────────────────────────┘

 [ ESP32: TWAI Driver ] (Pinos: TX=GPIO 4, RX=GPIO 5)
           │
           ▼ Linha Diferencial CAN_H / CAN_L a 500 kbaud
 [ Transceptor SN65HVD230 ]
           │
           ▼ Porta de Diagnóstico OBD-II do Veículo (VW Polo)
 [ ECU do Carro (Engine Control Module - ECM) ]
           │
           ├─► Envio: Broadcast ID 0x7DF | Modo 0x01 | PID (0x0C, 0x0D, 0x05)
           └─◄ Resposta: ECU ID 0x7E8 | Modo 0x41 | Dados dos PIDs em HEX
```

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| `hardware/esp32/CMakeLists.txt` | Criado | +4 / -0 | Arquivo raiz do projeto ESP-IDF invocando o meta-build CMake do framework. |
| `hardware/esp32/main/CMakeLists.txt` | Criado | +4 / -0 | Registro do componente de aplicação `main` e dependências dos drivers nativos. |
| `hardware/esp32/main/main.c` | Criado | +264 / -0 | Firmware inicial em C contendo o driver TWAI, tarefas FreeRTOS de transmissão/recepção e decodificação ISO 15765-4. |
| `hardware/esp32/sdkconfig` | Criado | +3734 / -0 | Configurações de compilação geradas pelo Kconfig (CPU em 240 MHz, FreeRTOS em 1000 Hz). |
| `.gitignore` | Modificado | +12 / -1 | Atualização de filtros para descartar a pasta `hardware/esp32/build/`. |
| `test/arduino/mqtts_test/mqtts_test.ino` | Movido | +0 / -0 | Realocação do protótipo preliminar de `src/` para o diretório de testes `test/`. |

---

## 3. Detalhamento Técnico das Modificações

### 3.1. Configuração do Driver TWAI a 500 kbaud (`main.c`)
* **Parâmetros de Temporização:** Utilização da macro canônica `TWAI_TIMING_CONFIG_500KBITS()`, que sincroniza o controlador do ESP32 com a taxa nominal de 500 kbps do barramento CAN automotivo.
* **Mapeamento de Pinos:** Configuração dos pinos digitais conectados ao transceptor SN65HVD230:
  * `CAN_TX_PIN = GPIO 4`
  * `CAN_RX_PIN = GPIO 5`
* **Modo Operacional:** `TWAI_MODE_NORMAL`, habilitando o microcontrolador tanto para escuta quanto para transmissão ativa de frames com geração de bits de reconhecimento (*ACK*).
* **Filtro de Aceitação:** `TWAI_FILTER_CONFIG_ACCEPT_ALL()`, garantindo que todas as respostas da ECU transitem para a pilha de aplicação.

### 3.2. Tarefas Concorrentes FreeRTOS

#### A. Tarefa de Transmissão Periódica (`twai_transmit_task`)
* Opera em loop cíclico com cadência de 100 ms disparando requisições OBD-II com frames padrão CAN (11 bits de identificador, DLC = 8):
  * **Identificador:** Broadcast `0x7DF` (padrão de diagnóstico ISO 15765-4).
  * **Comprimento de Dados (DLC):** 8 bytes.
  * **Byte 0:** Quantidade de bytes de dados adicionais (`0x02`).
  * **Byte 1:** Modo de Diagnóstico (`0x01` — Exibição de Dados Atuais da Telemetria).
  * **Byte 2:** Código do PID solicitado:
    * `0x0C`: Rotações por Minuto do Motor (RPM).
    * `0x0D`: Velocidade Veicular (km/h).
    * `0x05`: Temperatura do Líquido de Arrefecimento (°C).
  * **Bytes 3 a 7:** Preenchimento com bytes de enchimento (`0x55` ou `0xAA`).

#### B. Tarefa de Recepção e Decodificação (`twai_receive_task`)
* Escuta a fila de recepção do driver TWAI (`twai_receive`).
* Ao capturar um pacote com o identificador de resposta da ECU (`0x7E8`), valida o modo de resposta (`0x41` = Modo 0x01 + 0x40) e aplica as equações matemáticas normatizadas pela SAE J1979:
  * **RPM (PID 0x0C):**
    $$\text{RPM} = \frac{(A \times 256) + B}{4}$$
  * **Velocidade (PID 0x0D):**
    $$\text{Velocidade} = A \text{ km/h}$$
  * **Temperatura (PID 0x05):**
    $$\text{Temperatura} = A - 40 \text{ °C}$$
* Emissão dos valores decodificados no Monitor Serial via macro formatada `ESP_LOGI`.

---

## 4. Sinalização e Diagnóstico Visual de Hardware

Foram configurados dois pinos GPIO para fornecer confirmação imediata durante os ensaios físicos em bancada e no veículo:
* **Pino D13 (GPIO 13 — `PIN_CONFIRMA_ENERGIA`):** Nível lógico alto contínuo indicando que o driver TWAI foi inicializado com sucesso e o barramento está ativo.
* **Pino D14 (GPIO 14 — `PIN_CONFIRMA_DADOS`):** Pulso luminoso disparado a cada resposta válida recebida da ECU do veículo (ID `0x7E8`).

---

## 5. Avaliação Técnica e Gargalos Identificados (Roteiro para a Semana 4)

Embora a comunicação no barramento físico tenha sido bem-sucedida, a revisão técnica do código identificou dois gargalos críticos a serem solucionados:
1. **Delay Bloqueante na Recepção:**  
   O uso de `vTaskDelay(pdMS_TO_TICKS(40))` dentro da task de recepção (utilizado provisoriamente para manter o LED D14 aceso de forma perceptível) bloqueava a tarefa, gerando alto risco de estouro da fila TWAI (`s_rx_queue`) e descarte de frames em tráfego veicular intenso.
2. **Código Monolítico em Arquivo Único:**  
   O arquivo `main.c` concentrou inicialização de hardware, drivers, manipulação de GPIOs e decodificação de PIDs em ~270 linhas. Para a inclusão das camadas de Wi-Fi, TLS e cliente MQTT prevista na Semana 4, tornou-se mandatória a refatoração para uma **Arquitetura Baseada em Componentes (CBA)** governada por CMake.
