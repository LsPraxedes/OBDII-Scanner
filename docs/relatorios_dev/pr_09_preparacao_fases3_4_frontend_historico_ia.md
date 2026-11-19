# Pull Request #09: Preparação Fases 3 e 4 — Backend Temporal, Modularização do Frontend, Histórico Interativo e Páginas Visualizador-First (EDA & IA)

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Arquitetura de Frontend Modular, Consultas Temporais RESTful e Scaffolding Visual (Fases 3 e 4)  
**Commit Associado:** `3636da2` (`(feat): add temporal telemetry API, modular sidebar frontend and phase 3/4 views`)  
**Data:** 16 de Novembro de 2026  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`

---

## 1. Resumo Executivo e Objetivos

Seguindo a mesma metodologia adotada na transição da Fase 1 para a Fase 2 (**construir primeiro o visualizador e os contratos de visualização antes de treinar e implantar o objeto de estudo**), este marco prepara toda a camada de apresentação e consulta temporal do sistema para as **Fases 3 (Semanas 6–7: CRISP-DM / EDA e Isolation Forest)** e **4 (Semana 8: Implantação e Alertas)** — sem antecipar o treinamento nem a inferência de Machine Learning antes da etapa correspondente do cronograma.

A mudança endereçou duas limitações práticas identificadas durante o uso real do dashboard no carro:

1. O endpoint `GET /api/v1/telemetry` retornava por padrão apenas os últimos `100` registros (~100 segundos a 1 Hz), impedindo a análise de viagens completas.
2. O loop contínuo `while True:` com `placeholder.container()` no `streamlit==1.32.2` recriava os gráficos a cada `0,5 s`, **resetando zoom, arraste e barra de rolagem** durante a inspeção pelo usuário.

A solução manteve exatamente `streamlit==1.32.2` (com `altair==5.5.0` nativo), substituindo o arquivo único por uma **arquitetura modular com navegação lateral (`st.sidebar.radio`)** composta por quatro visões independentes e extensão retrocompatível da API REST do FastAPI.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               ARQUITETURA MODULAR DO DASHBOARD E BACKEND TEMPORAL                      │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ frontend/app.py ] ── Navegação Lateral (st.sidebar.radio)
   │
   ├─► 1. [ views/live.py ]          ── Tempo Real (100..1800 amostras + Pausa c/ Zoom/Pan)
   ├─► 2. [ views/history.py ]       ── Histórico por Dia (Slider BRT + Altair Overview+Detail + CSV)
   ├─► 3. [ views/eda.py ]           ── Preparação Semana 6 (CRISP-DM: describe, histogramas, dispersão)
   └─► 4. [ views/ai_diagnostics.py ]── Preparação Semanas 7–8 (Visualizador-First: Score & Feed Alertas)
               ▲
               │ HTTP REST (JSON)
 [ backend/main.py ]
   ├─► GET /api/v1/telemetry?limit=...&start_time=...&end_time=...
   └─► GET /api/v1/telemetry/days?tz_offset_minutes=-180
               │
               ▼
 [ SQLite: vehicle_data.db ] ── Índice ix_telemetry_timestamp (consultas rápidas por dia)
```

### Objetivos Alcançados

1. **Consultas Históricas Rápidas no Backend:** criação de índice temporal no SQLite, suporte a janela `start_time`/`end_time`, expansão segura de `limit` (`<= 50000`) e novo endpoint `GET /api/v1/telemetry/days` com ajuste de fuso horário (`UTC-3`).
2. **Controle de Janela e Modo Pausa em Tempo Real:** janela configurável (`100`, `300`, `600`, `1800` amostras) e congelamento opcional do `Auto-Refresh` para zoom/arraste interativo sem retorno ao início.
3. **Página Dedicada de Histórico e Viagens:** seleção por dia civil, filtro por horário, gráfico **Overview + Detail** no Altair atuando como barra de rolagem/zoom sincronizada entre todos os sensores e exportação CSV para coleta de datasets da Fase 3.
4. **Páginas Preparatórias para Fases 3 e 4:** criação das telas estruturais **Análise de Padrões (EDA)** (já conectada às estatísticas descritivas reais do banco) e **Diagnóstico Preditivo (IA)** (esqueleto visual pronto para receber o `.pkl` do *Isolation Forest* e os alertas nas Semanas 7–8).

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas / Diff | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| [backend/database.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/database.py) | Modificado | +1 / -1 (35 totais) | Adição de `index=True` na coluna `Telemetry.timestamp`. |
| [backend/schemas/telemetry.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/schemas/telemetry.py) | Modificado | +15 / -2 (34 totais) | Inclusão do schema `TelemetryDaySummary` usando `ConfigDict`. |
| [backend/main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/main.py) | Modificado | +82 / -10 (142 totais) | Índice `ix_telemetry_timestamp`, helper `normalize_to_naive_utc`, parâmetros de filtro em `/api/v1/telemetry` e endpoint `/api/v1/telemetry/days`. |
| [frontend/telemetry_utils.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/telemetry_utils.py) | Criado | 297 linhas | Cliente HTTP, conversão `local_day_to_utc_range` (`BRT`), `prepare_telemetry_dataframe`, `compute_acceleration`, `downsample_for_chart` e builders Altair. |
| [frontend/views/**init**.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/__init__.py) | Criado | 3 linhas | Definição do subpacote modular de visões do Streamlit. |
| [frontend/views/common.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/common.py) | Criado | 46 linhas | Helper reutilizável `select_and_load_day_dataframe` compartilhado entre Histórico, EDA e IA. |
| [frontend/views/live.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/live.py) | Criado | 190 linhas | Visão `Tempo Real` com `render_dashboard` (modo contínuo e modo pausado interativo). |
| [frontend/views/history.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/history.py) | Criado | 111 linhas | Visão `Histórico & Viagens` com slider horário, gráficos Altair *Overview + Detail*, KPIs da viagem e download CSV. |
| [frontend/views/eda.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/eda.py) | Criado | 76 linhas | Visão preparatória da Semana 6 (`CRISP-DM / EDA`): tabela `describe()`, histogramas e dispersão `Temperatura vs RPM`. |
| [frontend/views/ai_diagnostics.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/ai_diagnostics.py) | Criado | 67 linhas | Esqueleto visual *Visualizador-First* das Semanas 7–8 (`Isolation Forest`): cards de saúde, timeline base e contrato da tabela de alertas. |
| [frontend/app.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/app.py) | Refatorado | +64 / -68 (76 totais) | Ponto de entrada limpo com `st.sidebar.radio` e re-exportação compatível dos helpers testados. |
| [backend/tests/test_main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_main.py) | Modificado | +62 / -4 (122 totais) | Teste `test_read_telemetry_time_filter_and_days_summary` cobrindo fuso `-03:00` e endpoint `/days`. |
| [backend/tests/test_frontend_and_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_frontend_and_e2e.py) | Expandido | 327 linhas | Adição de testes para conversão `UTC-3`, amostragem `downsample_for_chart`, specs Altair e execução das 4 páginas no `AppTest`. |

---

## 3. Detalhamento Técnico das Modificações

### 3.1. Backend Temporal e Consistência de Fuso Horário (`backend/`)

* **Normalização UTC na Consulta (`normalize_to_naive_utc`):**  
  Como [database.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/database.py#L25) grava `timestamp` em UTC no SQLite sem metadado de fuso (`naive UTC`), o helper `normalize_to_naive_utc` em [main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/main.py#L29-L36) converte filtros recebidos com offset local (ex.: `-03:00`) para UTC antes da comparação SQL, garantindo precisão em viagens noturnas próximas à meia-noite.
* **Agrupamento por Dia Local (`/api/v1/telemetry/days`):**  
  Utiliza `func.date(Telemetry.timestamp, f"{tz_offset_minutes:+d} minutes")` diretamente no SQLite para agrupar datas civis no fuso brasileiro (`-180` minutos padrão) retornando `TelemetryDaySummary` (`date`, `count`, `first_timestamp`, `last_timestamp`) em ordem decrescente.
* **Indexação Sem Migração Destrutiva:**  
  A instrução `CREATE INDEX IF NOT EXISTS ix_telemetry_timestamp ON telemetry (timestamp)` executada na inicialização cria o índice automaticamente mesmo em bancos `vehicle_data.db` já existentes.

### 3.2. Navegação Lateral e Gráficos Sem Reset (`frontend/`)

* **Por que Navegação Lateral em `streamlit==1.32.2`:**  
  Na versão `1.32.2` mantida em [requirements.txt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/requirements.txt), não há `@st.fragment(run_every=...)`, e `st.tabs` executa todas as abas no mesmo script. Colocar o loop `while True:` dentro de `st.tabs` bloquearia ou reiniciaria os widgets das demais abas. O roteamento via `st.sidebar.radio` isola o loop exclusivamente na página **`📡 Tempo Real`**, mantendo **`📅 Histórico & Viagens`**, **`📊 Análise de Padrões (EDA)`** e **`🤖 Diagnóstico Preditivo (IA)`** 100% responsivas e estáticas durante a inspeção.
* **Barra de Rolagem e Zoom Sincronizado (`build_overview_detail_charts`):**  
  Utilizando `altair==5.5.0`, a página de histórico exibe um mini-gráfico superior de contexto com `alt.selection_interval(encodings=["x"])` vinculado ao domínio `x` dos 4 gráficos detalhados abaixo (`RPM`, `Velocidade`, `Temperatura` e `Aceleração`). Arrastar ou redimensionar essa seleção funciona como barra de rolagem horizontal e zoom sincronizado sem jamais retornar ao início.
* **Proteção de Performance no Navegador (`downsample_for_chart`):**  
  Para dias muito longos (`> 3000` amostras), o renderizador Altair recebe uma subamostragem uniforme preservando início e fim (`MAX_CHART_POINTS = 3000`), enquanto os KPIs, estatísticas descritivas e a exportação CSV operam sempre sobre 100% dos registros originais.

### 3.3. Páginas *Visualizador-First* para as Fases 3 e 4

* **[views/eda.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/eda.py) (Semana 6 — CRISP-DM):** apresenta `df.describe()` (média, desvio padrão, quartis, mínimo e máximo), histogramas de `RPM`, `Temperatura` e `Velocidade`, dispersão térmica `Temperatura vs RPM` sobre dados reais do dia e área reservada para a matriz de correlação e faixas normais de operação.
* **[views/ai_diagnostics.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/ai_diagnostics.py) (Semanas 7–8 — Isolation Forest & Alertas):** exibe o contrato visual completo — cards de estado do modelo `.pkl` e saúde do motor, série temporal base preparada para sobreposição do `anomaly_score` e tabela estrutural do feed de alertas (`Timestamp`, `Severidade`, `Tipo de Anomalia`, `Score Isolation Forest`, `RPM`, `Temperatura`, `Velocidade`, `Status`) — evitando gerar falsos alertas simulados até a integração real da IA.

---

## 4. Avaliação Comparativa: Antes (Semana 5) vs. Nova Arquitetura

| Critério Técnico | Versão Inicial Semana 5 | Nova Arquitetura Modular (PR #09) |
| :--- | :--- | :--- |
| **Alcance de Visualização** | Fixo nos últimos `100` registros | Tempo real (`100` a `1800`) + Histórico completo por dia (`<= 50000`) |
| **Navegação e Zoom nos Gráficos** | Resetava a cada `0,5 s` pelo loop `while True:` | Modo Pausa ao vivo + Histórico estático com *Overview + Detail* e slider BRT |
| **Organização do Código Frontend** | Arquivo único (`frontend/app.py`) | Camada de utilitários (`telemetry_utils.py`) + 4 páginas isoladas em `frontend/views/` |
| **Consultas ao SQLite** | Sem índice em `timestamp`; sem filtro temporal | Índice `ix_telemetry_timestamp` + filtros UTC + endpoint `/api/v1/telemetry/days` |
| **Aderência ao Fuso Local (BRT)** | Exibição dependente de conversão padrão | Conversão explícita `UTC-3` na busca por dia, sliders e eixos dos gráficos |
| **Preparação para Fases 3 e 4** | Sem espaço estrutural para EDA/IA | Páginas dedicadas de `EDA` e `Diagnóstico IA` prontas para plug-in nas Semanas 6–8 |

---

## 5. Plano de Validação e Testes Automatizados

* **Suíte de Testes (`pytest` no `venv`):**  
  **16/16 testes aprovados** em `5,25 s`:
  * [test_main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_main.py): 4 testes aprovados, incluindo `test_read_telemetry_time_filter_and_days_summary` validando borda de fuso `-03:00` (`22:30 BRT` mapeando corretamente para o dia anterior em relação a `01:30 UTC`).
  * [test_mqtt.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_mqtt.py): 3 testes de ingestão e validação Pydantic aprovados.
  * [test_frontend_and_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_frontend_and_e2e.py): 9 testes aprovados, cobrindo `local_day_to_utc_range`, `downsample_for_chart`, compilação dos specs Altair (`to_dict()`) e execução das visões `live_paused`, `history`, `eda` e `ai` dentro do motor real do Streamlit (`AppTest`).
* **Linter de Código (`ruff check backend frontend scripts`):**  
  Concluído com **`0` erros** (código de saída `0`).
