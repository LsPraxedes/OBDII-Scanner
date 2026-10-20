# Pull Request #01: Spike Exploratório — Prova de Conceito MQTTS no ESP32 (Arduino IDE)

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Hardware / Prova de Conceito Preliminar  
**Commit Associado:** [`eba1297eebe94d09b2f1bc4383282587c6138ae1`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `eba1297`)  
**Data:** 20 de Agosto de 2026 às 11:06:28 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Antes de iniciar a implementação do firmware de produção em baixo nível, foi conduzido um *Spike* tecnológico (Prova de Conceito exploratória) com o ecossistema Arduino para o ESP32.

O objetivo foi avaliar a viabilidade física e o comportamento do microcontrolador ESP32 DevKit V1 ao estabelecer conexões cifradas de rede utilizando **MQTTS (MQTT sobre TLS na porta 8883)**, validando o aperto de mão criptográfico (*TLS handshake*) com validação de Autoridade Certificadora (CA) contra o broker público `test.mosquitto.org`.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   SPIKE DE TRANSMISSÃO MQTTS (ARDUINO)                 │
└────────────────────────────────────────────────────────────────────────┘

 [ ESP32 DevKit V1 ] (Core Arduino: WiFiClientSecure + PubSubClient)
         │
         │ Conexão Wi-Fi Station
         ▼
 [ Ponto de Acesso / Hotspot Móvel ]
         │
         │ Handshake TLS v1.2 (Porta 8883 / Certificado Raiz X.509)
         ▼
 [ Broker Mosquitto: test.mosquitto.org:8883 ]
         │
         ▼ Publicação de Telemetria Simulada (JSON)
```

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| `src/arduino/mqtts_test/mqtts_test.ino` | Criado | +134 / -0 | Sketch em C++ (Arduino Core) com cliente Wi-Fi seguro e publicação MQTT cifrada. |
| [README.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/README.md) | Modificado | +72 / -1 | Introdução das primeiras diretrizes teóricas, escopo do VW Polo Track e barramento CAN. |

---

## 3. Detalhamento Técnico das Modificações

### 3.1. Implementação do Sketch de Teste (`mqtts_test.ino`)
* **Gerenciamento de Rede Segura:** Emprego da biblioteca `WiFiClientSecure` do ESP32 para lidar com a pilha TLS (mbedTLS encapsulada).
* **Injeção do Certificado Raiz X.509:** O certificado da CA do Mosquitto foi embutido diretamente no sketch como uma constante em memória Flash (`const char* root_ca`), injetada no cliente seguro via `espClient.setCACert(root_ca)`.
* **Publicação Periódica com PubSubClient:** Conexão ao broker `test.mosquitto.org` na porta 8883, com loop de reconexão automática e despacho periódico de cargas telemáticas simuladas para avaliar a taxa de perda de pacotes e a estabilidade da pilha TCP/IP.

### 3.2. Estruturação Conceitual no [README.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/README.md)
* Registro dos pilares do TCC: microcontrolador ESP32, protocolo de diagnóstico automotivo **ISO 15765-4 (CAN a 500 kbaud)**, ingestão em nuvem e posterior análise preditiva por Machine Learning.

---

## 4. Decisões de Engenharia e Lições Aprendidas

1. **Confirmação da Aceleração Criptográfica por Hardware:**  
   O processador Tensilica Xtensa Dual-Core do ESP32 demonstrou capacidade computacional plena para executar o algoritmo assimétrico RSA/ECC e as cifras AES-GCM do TLS sem causar latências severas na CPU.
2. **Identificação das Limitações do Arduino Core:**  
   Embora o teste tenha sido bem-sucedido na transmissão de rede, evidenciou-se que o Arduino Core abstrai excessivamente o hardware, dificultando:
   * O escalonamento determinístico de tarefas via FreeRTOS (prioridades estritas de interrupção).
   * O acesso a baixo nível aos registradores do driver de barramento **TWAI** (CAN nativo do chip).
   * A gestão granular de memória estática e alocação de pilhas (*stacks*).
3. **Decisão Arquitetural:**  
   Ficou formalmente deliberado que o firmware final do veículo deveria ser desenvolvido utilizando o framework industrial **ESP-IDF** em Linguagem C nativa.
