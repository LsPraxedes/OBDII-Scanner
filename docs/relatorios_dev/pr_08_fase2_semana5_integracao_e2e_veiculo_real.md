# Pull Request #08: Fase 2 (Semana 5) — Integração E2E no Veículo Real, Cálculo de Aceleração, Auditoria E2E e Recuperação Bus-Off CAN

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Integração Ponta a Ponta (E2E), Telemetria no Dashboard, Diagnóstico de Campo e Resiliência CAN/TWAI  
**Commit Associado:** `124d3fe` (`(alpha 2): e2e verify script, field guide and CAN bus-off auto-recovery`)  
**Data:** 16 de Novembro de 2026  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`

---

## 1. Resumo Executivo e Objetivos

Este relatório consolida todas as entregas da **Semana 5**, encerrando a **Fase 2: Cérebro do Carro (Hardware C/ESP-IDF)** e validando a esteira telemática ponta a ponta (**ECU do VW Polo $\rightarrow$ ESP32 CAN/TWAI $\rightarrow$ MQTTS TLS 8883 $\rightarrow$ FastAPI/SQLite $\rightarrow$ Dashboard Streamlit**) sob conexão móvel 4G real.

Além do refinamento da interface de visualização em tempo real, da criação de uma ferramenta CLI de auditoria de integridade (`scripts/verify_e2e.py`) e da formalização do guia operacional de ensaio em rodagem (`docs/guia_validacao_campo.md`), os testes práticos em campo revelaram um travamento do controlador TWAI em estado `node is bus off` quando o circuito tentava transmitir antes do barramento/ignição estabilizar — o que foi diagnosticado e corrigido diretamente no firmware embarcado com recuperação automática de *Bus-Off*.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              ESTEIRA E2E VALIDADA EM VEÍCULO REAL (SEMANA 5 — FASE 2)                 │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ VW Polo Track: Porta OBD-II ] ── CAN 500 kbaud (Pinos 6 CAN_H / 14 CAN_L)
               │
               ▼
 [ Transceptor SN65HVD230 + ESP32 ] (TX=GPIO 4, RX=GPIO 5 | LEDs: D13, D14, D26)
   ├─ obd2_can.c: Requisições 0x7DF + Auto-Recuperação de Bus-Off (twai_node_recover)
   ├─ wifi_manager.c: Hotspot 4G "POCO X7 Pro"
   └─ mqtt_service.c: Publicação JSON a cada 1000 ms (MQTTS / Porta 8883 / TLS v1.2)
               │
               ▼
 [ Backend FastAPI + Paho-MQTT + SQLite ] (vehicle_data.db)
               │
               ├──────────────────────────────┐
               ▼                              ▼
 [ frontend/app.py (Streamlit) ]   [ scripts/verify_e2e.py ]
   ├─ Badge Online/Offline (< 5 s)    ├─ Frequência média e ativa (Hz)
   ├─ Aceleração instantânea (m/s²)   ├─ Detecção de saltos anômalos (> 2,5 s)
   └─ Dispersão RPM vs Velocidade     └─ Estimativa de perda de pacotes 4G
```

### Objetivos Alcançados

1. **Correção de Bugs de Exibição no Dashboard ([frontend/app.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/app.py)):** eliminação de `IndexError` com apenas 1 registro no banco, proteção para `speed` opcional nulo (`Optional[float]`) e ordenação cronológica crescente antes da plotagem.
2. **Aceleração Real e Status de Conexão Ao Vivo:** cálculo de aceleração instantânea ($\Delta v / \Delta t$ em $\text{m/s}^2$) em métrica e gráfico dedicado, badge de status verde/vermelho com limiar de `5 s` e gráfico de relação **RPM vs Velocidade** para visualização de marchas.
3. **Auditoria E2E Automatizada ([scripts/verify_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/verify_e2e.py)):** monitoramento da API REST ou do SQLite com cálculo de frequência em Hz e detecção de saltos temporais.
4. **Roteiro de Ensaio em Campo ([docs/guia_validacao_campo.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/guia_validacao_campo.md)):** checklist passo a passo com Hotspot `POCO X7 Pro`, pinagem OBD-II e diagnóstico visual pelos LEDs `D13`, `D14` e `D26`.
5. **Resiliência do Barramento CAN ([obd2_can.c](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/obd2_can/obd2_can.c)):** tratamento automático de `TWAI_ERROR_BUS_OFF` evitando travamento permanente em `ESP_ERR_INVALID_STATE`.

---

## 2. Arquivos Modificados e Criados (Escopo Semana 5)

| Arquivo | Status | Tamanho / Diff | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| [frontend/app.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/app.py) | Refatorado (Etapa Semana 5) | 80 linhas originais (modularizado para 76 linhas no PR #09) | Tratamento de `len == 1` e `speed=None`, ordenação crescente UTC, cálculo de aceleração ($\Delta v / \Delta t$), badge Live/Offline `< 5 s` e dispersão `RPM vs Velocidade`. |
| [scripts/verify_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/verify_e2e.py) | Criado | 410 linhas | Utilitário CLI (`api`, `sqlite`, `auto` e `--watch`) para cálculo de frequência em Hz, intervalos e detecção de perda de pacotes/saltos anômalos. |
| [docs/guia_validacao_campo.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/guia_validacao_campo.md) | Criado | 79 linhas | Checklist operacional para testes reais no VW Polo Track (Hotspot 4G, chicote OBD-II, LEDs D13/D14/D26, Streamlit e pós-rodagem). |
| [hardware/esp32/components/obd2_can/obd2_can.c](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/obd2_can/obd2_can.c) | Modificado | +70 / -3 linhas (291 linhas no PR #08) | Callback `twai_state_change_cb` em ISR e função `twai_ensure_bus_ready` com recuperação automática via `twai_node_recover()`. |
| [backend/tests/test_frontend_and_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_frontend_and_e2e.py) | Criado | 327 linhas (com adições no PR #09) | Testes unitários da lógica de aceleração, ordenação, status `< 5 s`, análise E2E e renderização real com `streamlit.testing.v1.AppTest`. |

---

## 3. Detalhamento Técnico das Entregas

### 3.1. Refinamento Inicial do Dashboard ([frontend/app.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/app.py))

* **Correção de Indexação e Contratos Nulos:**  
  No código original da Semana 1, o acesso direto a `df.iloc[1]` provocava `IndexError` quando havia apenas 1 amostra, e `int(latest['speed'])` falhava quando `speed` vinha nulo (`Optional[float]` no schema [telemetry.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/schemas/telemetry.py), possível quando o ESP32 ainda não recebeu o PID `0x0D`). Foram implementadas `format_metric_delta` e verificação explícita `len(df) >= 2`.
* **Ordenação Cronológica e Fuso Horário:**  
  Como `GET /api/v1/telemetry` retorna linhas em ordem decrescente (`timestamp.desc()`), `prepare_telemetry_dataframe` normaliza `timestamp` para UTC (`pd.to_datetime(..., utc=True)`) e ordena crescentemente por `["timestamp", "id"]`, garantindo que os gráficos fluam da esquerda para a direita e o sinal da derivada temporal fique correto.
* **Cálculo da Aceleração Instantânea ($\text{m/s}^2$):**  
  Convertendo a velocidade de $\text{km/h}$ para $\text{m/s}$ ($v_{\text{m/s}} = v_{\text{km/h}} / 3{,}6$), a função `compute_acceleration` calcula:
  $$a_i = \frac{v_{\text{m/s}, i} - v_{\text{m/s}, i-1}}{t_i - t_{i-1}}$$
  Valores com $\Delta t \le 0$ ou velocidade ausente recebem `NaN` para evitar `ZeroDivisionError` ou infinitos.
* **Status de Conexão (`< 5 s`) e Análise de Marchas:**  
  `get_connection_status` compara o último `timestamp` em UTC com o horário atual: abaixo de `5,0 s` exibe `🟢 Veículo Conectado / Online (Transmissão 4G Ativa)`; acima ou igual, exibe `🔴 Sinal Desconectado / Carro Desligado`. Em seguida, um gráfico de dispersão relaciona `Velocidade (km/h)` e `Rotação (RPM)` evidenciando visualmente as retas de cada marcha.

### 3.2. Auditoria de Telemetria E2E ([scripts/verify_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/verify_e2e.py))

* **Modos de Coleta:** suporta `--source api`, `--source sqlite` ou `--source auto` (tenta a API REST local e realiza fallback transparente para o arquivo `vehicle_data.db`), além da flag `--watch` para acompanhamento contínuo no terminal.
* **Métricas Calculadas (`analyze_telemetry_records`):**
  * Contagem total persistida no SQLite e amostra analisada; contagem de registros sem `speed`.
  * Frequência média global na janela ($\text{Hz}$) e frequência ativa ($\text{Hz}$), isolando pausas longas entre sessões distintas (`> 60 s`) de perdas pontuais intra-sessão.
  * Detecção de saltos anômalos acima de `--gap-threshold` (padrão $\max(2{,}5\text{ s},\; 2{,}5 \times \Delta t_{\text{esperado}})$), estimando pacotes perdidos e taxa percentual de perda.

### 3.3. Recuperação Automática de *Bus-Off* no Firmware ([obd2_can.c](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/obd2_can/obd2_can.c))

Durante os testes práticos no circuito físico, o monitor serial registrou `APP_MAIN: Todos os modulos foram inicializados com sucesso!` seguido imediatamente por:

```text
E (4588) esp_twai: _node_queue_tx(608): node is bus off
W (4588) OBD2_CAN: Falha ao enviar requisicao OBD2 para PID 0x0D (err: ESP_ERR_INVALID_STATE)
```

O diagnóstico identificou que, se o ESP32 iniciar transmissões antes de a ECU/ignição estar pronta (ou após um erro físico transitório no barramento), o controlador TWAI entra em `TWAI_ERROR_BUS_OFF` e o código anterior não possuía rotina de recuperação, permanecendo travado em `ESP_ERR_INVALID_STATE`.

**Solução implementada em [`obd2_can.c`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/obd2_can/obd2_can.c#L84-L158):**

1. Registro de `twai_state_change_cb` em `.on_state_change` (contexto ISR, usando variáveis `atomic_bool` de `<stdatomic.h>`): detecta transições para `TWAI_ERROR_BUS_OFF` e confirma o retorno para `TWAI_ERROR_ACTIVE`.
2. Criação de `twai_ensure_bus_ready()` executada antes de cada envio em `twai_transmit_task`: consulta `twai_node_get_info()`, aciona `twai_node_recover(s_twai_node)` quando em `TWAI_ERROR_BUS_OFF` e suspende novas tentativas de TX (com aviso periódico a cada ~5 s) até o hardware completar as 128 sequências recessivas no barramento e retomar as requisições OBD-II automaticamente.

---

## 4. Decisões de Arquitetura e Engenharia de Software

1. **Zero Regressão nos Contratos da API e Schema:**  
   Nenhuma alteração incompatível foi introduzida em `TelemetryCreate` ou nos tópicos/payloads MQTTS do ESP32 já gravado, preservando integralmente o contrato RESTful `/api/v1/` e a validação Pydantic do backend.
2. **Separação entre Pausas de Sessão e Perdas de Rede no `verify_e2e.py`:**  
   Bancos reais acumulam sessões de dias/horários diferentes; separar pausas `> 60 s` evita distorcer a taxa média de transmissão ativa ao auditar múltiplas viagens.
3. **Segurança em Contexto de Interrupção (ISR) no TWAI:**  
   Em conformidade com a API `esp_driver_twai` do ESP-IDF v6.1 (`esp_twai.h`), `twai_node_recover()` e `ESP_LOG*` não são chamados dentro de `twai_state_change_cb`, mas sim sinalizados via flags atômicas para execução segura na task FreeRTOS `twai_transmit_task`.

---

## 5. Validação, Testes e Evidências em Veículo Real

1. **Testes Automatizados e Linter (`venv`):**
   * `pytest`: 12/12 testes aprovados na conclusão das entregas iniciais da Semana 5 (posteriormente ampliados para 16/16 no PR #09).
   * `ruff check backend frontend scripts`: `0` erros.
2. **Compilação do Firmware ESP-IDF v6.1:**
   * Build incremental via `ninja -C hardware\esp32\build` concluído com código de saída `0`, gerando [`obd2_scanner.bin`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/build/obd2_scanner.bin) (`0xe4630` bytes; `11%` livres na partição de app).
3. **Auditoria de Sessão Real no Veículo (`16/11/2026`):**
   * Comando executado: `python scripts/verify_e2e.py --source sqlite --limit 972 --expected-interval 1.0`.
   * **Resultado observado:** `972` pacotes reais ingeridos em `1079,26 s` (~18 min) com **frequência média de `0,900 Hz`** (intervalo mediano **`1,009 s`**), `0` registros com `speed` nulo, RPM real entre `0,0` e `2281,0 RPM` e aquecimento do líquido de arrefecimento de `57,0 °C` até `95,0 °C`. Após o reinício e ajuste físico no carro, o usuário confirmou operação completa da esteira (totalizando `2074` registros limpos no dia `2026-11-16`).
