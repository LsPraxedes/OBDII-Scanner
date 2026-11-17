# Guia de Validação em Campo — Veículo Real (Semana 5)

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Veículo-Alvo:** Volkswagen Polo Track (Barramento ISO 15765-4 CAN a 500 kbaud)  
**Objetivo:** Validar a integração ponta a ponta (E2E) entre a ECU do veículo, o firmware ESP32, a rede 4G, o backend FastAPI/MQTTS e o dashboard Streamlit em condição real de rodagem.

---

## Pré-Requisitos na Estação de Monitoramento (Notebook)

Antes de ir para o veículo, garanta que a infraestrutura em nuvem/local esteja ativa dentro do `venv`:

1. **Ativar ambiente virtual:**
   ```powershell
   venv\Scripts\activate
   ```
2. **Subir o backend FastAPI + Worker MQTTS (`ls-praxedes/scanner-obd2/+`):**
   ```powershell
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
3. **Subir o dashboard Streamlit em um segundo terminal:**
   ```powershell
   streamlit run frontend/app.py
   ```
4. **Opcional — Abrir monitor de auditoria E2E em um terceiro terminal:**
   ```powershell
   python scripts/verify_e2e.py --watch --expected-interval 1.0
   ```

---

## Checklist Operacional no Veículo (Passo a Passo)

> [!CAUTION]
> **Segurança Viária:** Nunca opere o notebook, smartphone ou códigos durante a condução do veículo. Todos os ajustes físicos e validações no dashboard devem ser feitos com o carro estacionado em local seguro ou por um passageiro auxiliar.

### Etapa 1 — Ativação do Hotspot 4G (`POCO X7 Pro`)
- [ ] Ligar o roteamento Wi-Fi (Hotspot 4G) no smartphone **`POCO X7 Pro`** **antes** de energizar o ESP32.
- [ ] Confirmar que as credenciais do hotspot coincidem com [`wifi_manager.h`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/wifi_manager/include/wifi_manager.h) (`WIFI_SSID: "POCO X7 Pro"`).
- [ ] Confirmar que o pacote de dados 4G está ativo e com conectividade externa (o firmware bloqueia em `wifi_manager_init_and_wait()` até obter IP via DHCP e, em seguida, conecta em `mqtts://test.mosquitto.org:8883`).

### Etapa 2 — Conexão Elétrica e Barramento OBD-II no VW Polo
- [ ] Com a ignição **desligada**, conectar o chicote do transceptor **SN65HVD230** ao conector fêmea OBD-II do VW Polo:
  - **CAN_H** $\rightarrow$ Pino 6 do OBD-II
  - **CAN_L** $\rightarrow$ Pino 14 do OBD-II
  - **GND** $\rightarrow$ Pinos 4/5 do OBD-II
- [ ] Conferir alimentação **3.3V** no transceptor SN65HVD230 e pinos **TX = GPIO 4 / RX = GPIO 5** no ESP32.
- [ ] Girar a chave para **ignição ligada (estágio ACC/ON)** ou dar partida no motor e alimentar o ESP32.

### Etapa 3 — Checagem dos LEDs de Diagnóstico do ESP32
Acompanhe a sequência de inicialização pelos três LEDs de status definidos em [`obd2_can.h`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/obd2_can/include/obd2_can.h) e [`mqtt_service.h`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/mqtt_service/include/mqtt_service.h):

| LED / Pino | Comportamento Esperado | Diagnóstico se Falhar |
| :--- | :--- | :--- |
| **D13 (Power / Sistema Pronto)** | **Aceso contínuo** logo após `obd2_can_init()`. | Se apagado: falha na inicialização do driver TWAI ou ausência de alimentação no ESP32. |
| **D14 (Tráfego CAN)** | **Piscando continuamente** a cada resposta OBD-II (`0x7E8`) da ECU (~500 ms entre requisições de RPM `0x0C`, Velocidade `0x0D` e Temperatura `0x05`). | Se apagado: ignição desligada, fios `CAN_H`/`CAN_L` invertidos, falha no SN65HVD230 ou barramento fora de 500 kbaud. |
| **D26 (MQTTS / TLS 8883)** | **Piscando a cada 1 segundo** (`MQTT_PUB_INTERVAL_MS = 1000`), confirmando publicação JSON cifrada no broker Mosquitto. | Se apagado: ESP32 ainda aguardando Wi-Fi do hotspot `POCO X7 Pro`, queda de sinal 4G ou falha no handshake TLS com o broker. |

### Etapa 4 — Visualização e Validação no Dashboard Streamlit
- [ ] Acessar `http://localhost:8501` no notebook (ou IP da máquina na mesma rede pelo celular do passageiro).
- [ ] Confirmar o badge verde no topo do painel: **`🟢 Veículo Conectado / Online (Transmissão 4G Ativa)`**.
- [ ] Com o carro parado e motor ligado (marcha lenta):
  - Verificar **RPM** coerente (ex.: ~750–950 RPM após aquecimento), **Temperatura** crescente até regime térmico (~85–95 °C), **Velocidade** em `0 km/h` e **Aceleração Atual** em `0.00 m/s²`.
- [ ] Em trecho seguro com auxílio de passageiro (aceleração leve e frenagem):
  - Confirmar que os gráficos temporais fluem **da esquerda para a direita**.
  - Confirmar picos positivos de **Aceleração Atual (m/s²)** ao acelerar e valores negativos ao frear.
  - Verificar no gráfico **Análise de Condução (RPM vs Velocidade)** o surgimento das faixas lineares correspondentes às trocas de marcha.
- [ ] Ao desligar o carro / encerrar o teste:
  - Após 5 segundos sem novos pacotes, confirmar a transição automática do badge para **`🔴 Sinal Desconectado / Carro Desligado`**.

### Etapa 5 — Auditoria Pós-Rodagem
Executar no terminal para auditar taxa de amostragem e integridade da série temporal salva no SQLite:
```powershell
python scripts/verify_e2e.py --source sqlite --limit 1000 --expected-interval 1.0
```
Critérios de aprovação da Semana 5:
- Frequência média ativa próxima de **1.0 Hz** (intervalo mediano ~`1.0 s`).
- Baixa taxa de perda de pacotes estimada durante cobertura 4G estável.
- Ausência de registros com velocidade nula após estabilização da leitura CAN.
