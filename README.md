# 🚗 Central de Análise Veicular Preditiva (IoT)

![Status do Projeto](https://img.shields.io/badge/Status-Alpha_2-yellow)
![Hardware](https://img.shields.io/badge/Hardware-ESP32%20%7C%20CAN%20%7C%20ESP--IDF-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20MQTTS%20%7C%20Pydantic-brightgreen)
![Frontend](https://img.shields.io/badge/Frontend-Streamlit-red)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-GPL--3.0-orange)

Este repositório contém o código-fonte do Trabalho de Conclusão de Curso (TCC) em Engenharia da Computação, que propõe o desenvolvimento de um sistema computacional auxiliar para monitoramento, transmissão telemática segura e análise preditiva de dados veiculares de um **Volkswagen Polo Track (adaptado para o protocolo ISO 15765-4 CAN a 500 kbaud)**.

O objetivo é criar uma solução telemática de alta confiabilidade e baixo custo que atue como um computador de bordo inteligente, capaz de extrair telemetria veicular via barramento CAN, transmitir pacotes cifrados via **MQTTS (TLS 8883)**, armazenar séries temporais de forma determinística e empregar algoritmos de Machine Learning Clássico (IA) para prever anomalias mecânicas no motor.

---

## 🏗️ Arquitetura do Sistema

O projeto segue os princípios de **Engenharia de Sistemas Desacoplados (Borda $\rightarrow$ Nuvem $\rightarrow$ Visualização)**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ARQUITETURA GERAL DE TELEMETRIA VEICULAR                        │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ VW Polo Track: Porta OBD-II ] (Barramento ISO 15765-4 / CAN a 500 kbaud)
               │
               ▼ Linhas Diferenciais CAN_H / CAN_L
  [ Transceptor CAN SN65HVD230 ] (Pinos TX: GPIO 4 | RX: GPIO 5)
               │
               ▼
   [ Unidade Telemática ESP32 ] (Firmware Modular em C / ESP-IDF v6.1 & FreeRTOS)
        ├─ telemetry: Repositório com exclusão mútua via FreeRTOS Mutex
        ├─ obd2_can: Driver TWAI não-bloqueante com FreeRTOS Software Timer
        ├─ wifi_manager: Conexão Station resiliente com sincronização via EventGroup
        └─ mqtt_service: Cliente MQTTS (TLS 8883) com certificado X.509 e LED D26
               │
               ▼ Publicação MQTTS (Porta 8883 / TLS v1.2 / Broker Mosquitto)
    [ Broker Mosquitto ] ── Tópico: "ls-praxedes/scanner-obd2/esp32"
               │
               ▼ Assinatura Wildcard: "ls-praxedes/scanner-obd2/+"
   [ Backend FastAPI + Paho-MQTT ] ── Ingestão em background via Lifespan
               │
               ├─► Validação Estrita de Domínio com Pydantic v2 (TelemetryCreate)
               ├─► Persistência Transacional ACID com SQLAlchemy ORM
               └─► Banco de Dados Relacional SQLite (vehicle_data.db)
               ▲
               │ Consultas REST: GET /api/v1/telemetry
  [ Frontend Streamlit / Dashboard ] ── Visualização em tempo real e análise preditiva
```

---

## 🗓️ Cronograma de Desenvolvimento (Fases)

- [x] **Alpha 1 (Esteira de Dados Mock-First):** Setup FastAPI, Banco SQLite, Schemas Pydantic, MQTTS com TLS na porta 8883, Broker Mosquitto, Dashboard Streamlit e emulador `scripts/mock_car.py`.
- [x] **Alpha 2 (Hardware Embarcado ESP-IDF):** Leitura de PIDs da ECU (RPM 0x0C, Velocidade 0x0D, Temperatura 0x05) no barramento TWAI a 500 kbaud e refatoração para **Arquitetura Baseada em Componentes (CBA)** com transmissão MQTTS ponta a ponta.
- [ ] **Alpha 3 (IA Preditiva Clássica):** Metodologia CRISP-DM, limpeza com Pandas e modelagem de detecção de anomalias com Scikit-Learn (*Isolation Forest*).
- [ ] **Alpha 4 (Implantação e Alertas E2E):** Integração do modelo de Machine Learning no backend FastAPI para geração de alertas em tempo real no dashboard.
- [ ] **Beta 1 (Validação Final em Campo):** Ensaios de rodagem com o VW Polo Track, coleta de telemetria 4G e formatação final para a defesa do TCC.

---

## 📚 Documentação Técnica e Relatórios de Arquitetura

Para auditoria técnica detalhada, fundamentos teóricos e preparação para a banca examinadora, consulte os relatórios na pasta [`docs/`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs):

- **[Índice de Pull Requests por Commit](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/README.md):** Histórico completo de evolução do repositório dissecado commit a commit em relatórios dedicados de Pull Request.

- **[Relatório de Arquitetura Backend](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/docs/relatorio_arquitetura_backend.md):** Ingestão MQTTS, modelo Pub/Sub, regras formais de wildcards OASIS MQTT v3.1.1, Twelve-Factor App, modelagem de ameaças e Zero Trust (NIST SP 800-207).
- **[Relatório de Arquitetura Firmware ESP-IDF](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/docs/relatorio_arquitetura_firmware_cmake.md):** Component-Based Architecture (CBA / ISO/IEC/IEEE 42010), sistema de build CMake/Ninja, FreeRTOS Mutex, timers assíncronos e diretrizes MISRA-C.

---

## 🔧 Compilação e Gravação do Firmware ESP32 (ESP-IDF)

O firmware embarcado foi desenvolvido em **Linguagem C** utilizando o framework oficial **ESP-IDF v6.1** da Espressif sob o sistema de build **CMake** e gerador **Ninja**.

### 1. Requisitos de Ferramental

- **Microcontrolador:** ESP32 DevKit V1 (ESP32-WROOM-32).

- **Transceptor CAN:** Módulo SN65HVD230 (alimentado a 3.3V).
- **ESP-IDF:** Versão 6.1 (ou compatível com v5.x).
- **Driver USB-UART:** Silicon Labs CP2102 ou WCH CH340 instalado no sistema operacional.
- **Cabo de Comunicação:** Cabo Micro-USB com linhas de dados ativas (não apenas carga).

---

### 2. Mapeamento de Pinos e Conexão Elétrica

| Pino ESP32 | Identificação | Direção | Função no Sistema | Conexão Física |
| :---: | :---: | :---: | :--- | :--- |
| **GPIO 4** | D4 | Saída (TX) | Linha de Transmissão TWAI/CAN | Pino `CTX` (ou `TXD`) do transceptor SN65HVD230 |
| **GPIO 5** | D5 | Entrada (RX) | Linha de Recepção TWAI/CAN | Pino `CRX` (ou `RXD`) do transceptor SN65HVD230 |
| **GPIO 13** | D13 | Saída Digital | LED de Status: Alimentação / TWAI Ativo | LED integrado ou resistor + LED externo para GND |
| **GPIO 14** | D14 | Saída Digital | LED de Status: Pacote CAN Recebido (ECU 0x7E8) | LED integrado ou resistor + LED externo para GND |
| **GPIO 26** | D26 | Saída Digital | LED de Status: Pacote MQTTS Transmitido | LED integrado ou resistor + LED externo para GND |
| **3V3** | 3.3V | Alimentação | Tensão de Operação do Transceptor | Pino `3V3` do módulo SN65HVD230 |
| **GND** | GND | Referência | Terra Comum | Pino `GND` do módulo SN65HVD230 e pino 4/5 do conector OBD-II |
| **CAN_H** | - | Diferencial | Linha Alta do Barramento Automotivo | Pino 6 do Conector Fêmea OBD-II do Carro |
| **CAN_L** | - | Diferencial | Linha Baixa do Barramento Automotivo | Pino 14 do Conector Fêmea OBD-II do Carro |

> [!WARNING]
> O módulo transceptor SN65HVD230 opera com nível lógico e alimentação de **3.3V**, o que é ideal para o ESP32. Não conecte transceptores de 5V (como MCP2551) diretamente aos pinos do ESP32 sem conversores de nível lógico bidirecionais, sob risco de queimar os pinos GPIO.

---

### 3. Configurações Pré-Compilação

Antes de compilar, ajuste os parâmetros de conectividade no código-fonte do firmware se necessário:

1. **Credenciais Wi-Fi:**  
   Abra o arquivo [`hardware/esp32/components/wifi_manager/include/wifi_manager.h`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/wifi_manager/include/wifi_manager.h) e configure o SSID e Senha do seu hotspot 4G ou rede Wi-Fi local:

   ```c
   #define WIFI_SSID           "Seu_Hotspot_4G"
   #define WIFI_PASS           "sua_senha_wifi"
   #define WIFI_MAXIMUM_RETRY  10
   ```

2. **Parâmetros MQTTS:**  
   No arquivo [`hardware/esp32/components/mqtt_service/include/mqtt_service.h`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/mqtt_service/include/mqtt_service.h), confirme o endereço do broker e o tópico de telemetria:

   ```c
   #define MQTT_BROKER_URI      "mqtts://test.mosquitto.org:8883"
   #define MQTT_TOPIC           "ls-praxedes/scanner-obd2/esp32"
   #define MQTT_PUB_INTERVAL_MS 1000
   ```

   *O certificado CA do broker já se encontra embutido via `mosquitto.org.crt` no componente.*

3. **Parâmetros do Barramento TWAI (CAN):**  
   No arquivo [`hardware/esp32/components/obd2_can/include/obd2_can.h`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/obd2_can/include/obd2_can.h), os pinos TX=4 e RX=5 já vêm pré-configurados para a velocidade canônica do VW Polo (500 kbaud).

---

### 4. Passo a Passo de Compilação, Gravação e Monitoramento

#### Passo 4.1: Carregar o Ambiente do ESP-IDF

Abra o terminal na raiz do projeto ou utilize o terminal do VS Code:

- **No Windows PowerShell:**

  ```powershell
  . C:\esp\v6.1\esp-idf\export.ps1
  ```

- **No Windows Prompt de Comando (CMD):**

  ```cmd
  C:\esp\v6.1\esp-idf\export.bat
  ```

- **No Linux / macOS:**

  ```bash
  . $HOME/esp/esp-idf/export.sh
  ```

*(Ou utilize a barra de status da extensão oficial do ESP-IDF no VS Code clicando em "ESP-IDF: Open ESP-IDF Terminal").*

#### Passo 4.2: Definir o Alvo de Hardware (Primeira Compilação)

Navegue até a pasta do firmware e defina o target:

```powershell
cd "hardware\esp32"
idf.py set-target esp32
```

#### Passo 4.3: Compilar o Projeto

Execute a compilação gerenciada pelo CMake e Ninja:

```powershell
idf.py build
```

O compilador `xtensa-esp32-elf-gcc` irá compilar os componentes isolados (`telemetry`, `obd2_can`, `wifi_manager`, `mqtt_service`) e o linker gerará o binário executável `build/obd2_scanner.bin`.

#### Passo 4.4: Gravar o Firmware na Memória Flash

Conecte o ESP32 ao computador via USB. Identifique a porta COM designada (ex: `COM3`, `COM4` no Windows, ou `/dev/ttyUSB0` no Linux) e execute:

```powershell
idf.py -p COM3 flash
```

#### Passo 4.5: Abrir o Monitor Serial

Para acompanhar o boot do sistema, o diagnóstico dos drivers e a saída em tempo real:

```powershell
idf.py -p COM3 monitor
```

*(Para encerrar a visualização do monitor serial, pressione `Ctrl + ]`).*

> [!TIP]
> Você pode compilar, gravar e abrir o monitor em um único comando:
>
> ```powershell
> idf.py -p COM3 flash monitor
> ```

---

### 5. Guia Visual de Diagnóstico dos LEDs

Durante a operação em bancada ou no veículo real, acompanhe os LEDs para confirmação do estado do sistema:

1. **LED D13 (Power / TWAI Pronto):**  
   Fica aceso contínuo assim que a função `obd2_can_init()` conclui a inicialização com sucesso. Se permanecer apagado, ocorreu erro de alocação de hardware do driver TWAI.
2. **LED D14 (Atividade do Barramento CAN):**  
   Pisca rapidamente a cada frame de resposta OBD-II (`0x7E8`) recebido da ECU do veículo. Se o carro estiver com a ignição desligada ou o transceptor desconectado, o LED permanecerá apagado.
3. **LED D26 (Transmissão MQTTS Segura):**  
   Pisca a cada 1 segundo confirmando que o pacote JSON foi publicado com sucesso no Broker Mosquitto via conexão TLS. Se o Wi-Fi estiver desconectado, o LED não piscará.

---

## 💻 Como Rodar o Ecossistema Completo (Nuvem / Backend / Dashboard)

### 1. Preparação do Ambiente Python

Certifique-se de estar com o ambiente virtual ativo na raiz do repositório:

```powershell
# 1. Ativar o venv
venv\Scripts\activate

# 2. Instalar / Atualizar dependências
pip install -r requirements.txt
```

### 2. Executar os Testes Automatizados

Valide a integridade dos contratos Pydantic e da mensageria:

```powershell
python -m pytest
```

### 3. Iniciar o Servidor Backend (FastAPI + Worker MQTTS)

Em um terminal, inicie a API com Uvicorn:

```powershell
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- A documentação interativa Swagger/OpenAPI estará acessível em: `http://localhost:8000/docs`

- O cliente MQTTS iniciará automaticamente em segundo plano via `lifespan`, escutando o tópico `ls-praxedes/scanner-obd2/+` na porta 8883.

### 4. Iniciar o Dashboard (Streamlit)

Em um segundo terminal:

```powershell
streamlit run frontend/app.py
```

O painel abrirá automaticamente no navegador em: `http://localhost:8501`.

### 5. Simulação sem Veículo Físico (Mock Car)

Caso queira testar a esteira completa sem o ESP32 físico conectado:

```powershell
python scripts/mock_car.py
```

O script publicará dados de telemetria dinâmicos no broker Mosquitto via TLS, alimentando o banco SQLite e os gráficos do Streamlit em tempo real.

---

## 🛡️ Cibersegurança e Boas Práticas

- **Criptografia em Trânsito:** Toda a comunicação telemática é cifrada via TLS v1.2 na porta 8883 utilizando certificados digitais X.509 da autoridade certificadora Mosquitto.
- **Validação Inflexível de Dados:** Nenhum dado atinge o banco de dados relacional sem passar pela sanitização estrita de limites físicos e semânticos realizada pelo Pydantic v2.
- **Proteção de Memória:** O firmware utiliza semáforos de exclusão mútua (**FreeRTOS Mutex**) e temporizadores assíncronos de software para impedir condições de corrida e estouro de filas de interrupção no barramento CAN.

---

## 👥 Autoria e Agradecimentos

- **Autor:** Lucas Praxedes
- **Orientação Acadêmica:** Trabalho de Conclusão de Curso (TCC) — Engenharia da Computação
- **Licença:** GNU General Public License v3.0 ([GPL-3.0](file:///c:/Users/lucas/Documents/OBDII%20Scanner/LICENSE))
