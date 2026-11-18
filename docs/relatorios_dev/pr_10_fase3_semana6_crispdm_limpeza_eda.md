# Pull Request #10: Fase 3 (Semana 6) — CRISP-DM: Entendimento e Preparação dos Dados, Qualidade dos Dados (Rajadas 4G) e EDA

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Pipeline de Limpeza com Pandas, Engenharia de Atributos, Análise Exploratória e Página EDA  
**Commit Associado:** *pendente* (alterações locais sobre `f850aa7`; versionamento a cargo do autor, conforme [AGENTS.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/AGENTS.md))  
**Data:** 18 de Novembro de 2026  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>` (com atuação do Agente Executor — Semana 6, [executor6.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/.gemini/agents/executor6.md))

---

## 1. Resumo Executivo e Objetivos

Este marco executa a **Semana 6 da Fase 3 (IA Preditiva Clássica)** do [planejador.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/.gemini/agents/planejador.md), cobrindo as etapas **Entendimento dos Dados** e **Preparação dos Dados** da metodologia CRISP-DM sobre os dados **reais** coletados no VW Polo Track (`vehicle_data.db`, 16/11/2026). Foi construído um pipeline **determinístico e reutilizável** em Pandas, consumido por três pontos: a CLI de auditoria (`scripts/run_eda.py`), a página `📊 Análise de Padrões (EDA)` do Streamlit e, na Semana 7, o treinamento do *Isolation Forest*.

Conforme a fronteira de escopo, **não** foi instalado `scikit-learn`, **não** houve treinamento e **nenhum** `.pkl` foi gerado.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                 PIPELINE CRISP-DM — SEMANA 6 (ENTENDIMENTO + PREPARAÇÃO)               │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ vehicle_data.db ] ──(sqlite3, somente leitura)──┐      [ API REST /api/v1/telemetry ]
                                                   ▼                     │
                     backend/ml/data_preparation.py :: prepare_dataset() ◄┘
                       1. normalize_raw_dataframe  (UTC, tipos, ordenação [timestamp, id])
                       2. clean_telemetry          (filtros físicos + Data Quality Report)
                       3. flag_4g_bursts           (is_burst dt<0,25 s | is_long_gap dt>2,5 s)
                       4. add_engineered_features  (acceleration_ms2, rpm_delta, rpm_per_speed)
                       5. classify_operating_regime(engine_off | idle | driving | unknown)
                       6. add_estimated_timestamp  (timestamp_est — apenas EDA, nunca treino)
                                                   │
                     backend/ml/eda_analysis.py ◄──┘
                       describe + P05/P95/P99 · por regime · correlação · limiares normais
                         │                                   │
                         ▼                                   ▼
             [ scripts/run_eda.py ]               [ frontend/views/eda.py ]
             terminal + --export-clean (CSV)      Bruto vs. Limpo · Heatmap · Regimes · Limiares
```

### Objetivos Alcançados
1. **Pipeline de limpeza e atributos** com filtros físicos do veículo e *Data Quality Report* contabilizando remoções por regra.
2. **Tratamento explícito das rajadas 4G**, que preserva as leituras e anula só os atributos derivados do tempo.
3. **EDA consolidada**: estatísticas globais e por regime, matriz de correlação e limiares normais preliminares.
4. **CLI de auditoria** com exportação do dataset limpo para pasta ignorada pelo Git.
5. **Página EDA completa**: o espaço reservado da Semana 6 foi substituído por quatro painéis novos, e os gráficos existentes foram preservados.

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| [backend/ml/\_\_init\_\_.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/ml/__init__.py) | Criado | 6 | Pacote de IA clássica (Fase 3). |
| [backend/ml/data_preparation.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/ml/data_preparation.py) | Criado | 334 | Carga SQLite tolerante, normalização, limpeza, rajadas, atributos, regimes, `timestamp_est`, `DataQualityReport`. |
| [backend/ml/eda_analysis.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/ml/eda_analysis.py) | Criado | 134 | `describe_with_percentiles`, `describe_by_regime`, `regime_distribution`, `compute_correlation_matrix`, `compute_normal_thresholds`, `build_eda_summary`. |
| [scripts/run_eda.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/run_eda.py) | Criado | 138 | CLI `--db`, `--export-clean`, `--output-dir` (padrão `data/clean/`). |
| [frontend/views/eda.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/views/eda.py) | Evoluído | 76 → 278 | Painéis Bruto vs. Limpo, heatmap Altair, comparação por regime (boxplot) e tabela de limiares. |
| [backend/tests/test_data_preparation.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_data_preparation.py) | Criado | 353 | 11 testes (limpeza, rajadas, regimes, `timestamp_est`, SQLite, EDA, CLI e `AppTest`). |
| [.gitignore](file:///c:/Users/lucas/Documents/OBDII%20Scanner/.gitignore) | Modificado | +5 | `data/`, `telemetry_*.csv`, `*.parquet`. Não foi usado `*.csv` global, que ignoraria os `partitions.csv` do ESP-IDF. |

Arquivos **não** alterados (fronteira de escopo): `docs/latex/TCC_II/`, `hardware/`, `backend/schemas/`, `frontend/views/ai_diagnostics.py`, `frontend/telemetry_utils.py`, `requirements.txt`.

---

## 3. Detalhamento Técnico

### 3.1. Regras de Limpeza (ordem de aplicação)
| # | Regra (`removed_by_rule`) | Critério |
| :-: | :--- | :--- |
| 1 | `invalid_timestamp` | timestamp não conversível (`format="ISO8601"`, `utc=True`) |
| 2 | `duplicates` | mesmo `timestamp` + `rpm` + `temperature` + `speed` |
| 3 | `missing_required_values` | `rpm` ou `temperature` nulos (`speed` é opcional no schema) |
| 4 | `speed_sentinel_255` | `speed == 255,0` (0xFF — PID 0x0D sem dado válido) |
| 5 | `rpm_out_of_range` | fora de `[0, 8000]` |
| 6 | `speed_out_of_range` | fora de `[0, 220]` km/h |
| 7 | `temperature_out_of_range` | fora de `[-20, 140]` °C |

### 3.2. Atributos e Regimes
* `acceleration_ms2` $= \Delta v_{\text{m/s}} / \Delta t$, calculada **apenas** quando `derivative_valid` (`0,25 s ≤ dt ≤ 2,5 s`) e $|a| \le 15\ \text{m/s}^2$.
* `rpm_delta` = ΔRPM entre amostras consecutivas com `derivative_valid`.
* `rpm_per_speed` = RPM / velocidade, somente com `speed > 5 km/h`. Funciona como assinatura da marcha engatada.
* **Regime:** `engine_off` (RPM < 300) · `driving` (speed > 2 km/h) · `idle` (motor ligado, speed ≤ 2 km/h) · `unknown` (motor ligado sem velocidade).

### 3.3. Robustez de Parsing do Timestamp
Durante os testes foi identificado que `pd.to_datetime` **sem formato explícito** infere o padrão pelo primeiro elemento. Strings ISO com e sem microssegundos na mesma coluna (ex.: `18:00:20+00:00` e `18:00:20.010000+00:00`) faziam as demais virarem `NaT`, e elas eram descartadas silenciosamente. O pipeline usa `format="ISO8601"`.
> **Achado para backlog (fora do escopo):** [`prepare_telemetry_dataframe`](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/telemetry_utils.py#L129) no frontend usa a conversão sem formato explícito e pode sofrer o mesmo efeito. O impacto prático é baixo, porque o SQLite grava microssegundos e só valores com microssegundo exatamente zero seriam afetados.

---

## 4. Qualidade dos Dados: Rajadas 4G e Análise de Decisão sobre o Timestamp

> Material preparado para a discussão sobre qual caminho tomar e para uso na monografia.  
> **Capítulo sugerido:** *Metodologia → nova subseção "Preparação e qualidade dos dados (CRISP-DM)"* (ou dentro de *"Emulação veicular, visualização em tempo real e modelagem da camada de detecção"*), com base teórica em *Fundamentação Teórica → "Mineração de dados (CRISP-DM)…"*. A alternativa E (firmware) cabe em *Metodologia → Engenharia de firmware embarcado* e em *Trabalhos futuros*.

### 4.1. O que é uma "rajada 4G"
O `timestamp` é gerado **no backend no momento da chegada** da mensagem MQTT ([database.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/database.py), `default=datetime.now(timezone.utc)`), e não no instante da leitura CAN. O firmware publica apenas `{"rpm","temperature","speed"}` a cada 1 s ([mqtt_service.c](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/esp32/components/mqtt_service/mqtt_service.c#L61-L67)). Quando o 4G do *hotspot* oscila ou cai, a pilha TCP/MQTT retém os pacotes e os entrega em lote quando o enlace volta. Eles chegam com cerca de 10 ms de diferença e recebem horários quase idênticos. As leituras são válidas; o horário é que está deslocado.

Exemplo real:

| Chegada (UTC) | RPM | Velocidade | Δt |
| :--- | :---: | :---: | :---: |
| 18:35:19.513 | 975 | 3 | 1,2 s (normal) |
| 18:35:46.925 | 744 | 3 | **27,4 s** (queda de sinal) |
| 18:35:46.938 | 975 | 3 | **0,013 s** ← rajada |

### 4.2. Evidências quantitativas (16/11/2026)
| Item | Resultado |
| :--- | :--- |
| Registros / dias | 2074 / 1 |
| Intervalo mediano entre chegadas | ≈ 1,008 s (nominal 1 Hz) |
| Rajadas (`dt < 0,25 s`) | **177 registros (8,5 %)**, em 71 grupos (mediana ≈ 0,013 s) |
| Tamanho dos grupos | 1 pacote: 31 · 2: 28 · 3–7: 7 · 10–12: 5 |
| Rajadas com RPM = 0 | **0**: não são efeito de ligar/desligar o carro |
| Rajadas com velocidade > 0 | **140 de 177**: ocorrem com o veículo em movimento |
| Quedas longas (`dt > 2,5 s`) | 24 |
| Maiores janelas de falha | 12,2 s / 18,6 s / 22,8 s, cada uma seguida de 12 pacotes |

### 4.3. Hipótese testada: redistribuir uniformemente os pacotes na janela de falha
Proposta do autor: dividir a janela da falha pelo número de pacotes do grupo (ex.: 10 pacotes em 15 s → 1,5 s cada) para estimar onde cada pacote deveria estar.

| Grupo | Janela | Pacotes | s/pacote |
| :--- | :---: | :---: | :---: |
| 18:36:36 | 12,2 s | 12 | **1,02** (coerente com 1 Hz) |
| 18:36:05 | 18,6 s | 12 | 1,55 (pacotes perdidos ou envio atrasado) |
| 18:38:55 | 22,8 s | 12 | 1,90 (idem) |
| 18:36:07 | 2,4 s | 11 | 0,22 (janela curta demais) |

**Somente 2 de 71 grupos** resultaram em ≈ 1 s/pacote. Causas: (i) perda de pacotes durante a falha, que deixa lacunas impossíveis de localizar; (ii) rajadas encadeadas que se sobrepõem; (iii) a redistribuição cria horários com aparência de reais, mas que são estimativas, e isso contamina os atributos derivados (aceleração).

### 4.4. Alternativas comparadas
| # | Alternativa | Vantagens | Limitações |
| :-: | :--- | :--- | :--- |
| A | Ignorar o timestamp (só atributos instantâneos) | Simples; não inventa dados | Perde aceleração e ΔRPM |
| **B** | **Manter timestamp + marcar rajadas + anular derivadas nelas** *(implementada)* | Preserva 100 % das leituras; transparente | Derivadas indisponíveis em ~8,5 % das linhas (+ quedas longas) |
| C | Redistribuição uniforme na janela de falha | Recupera atributos dinâmicos | Só ~3 % dos grupos coerentes; horários fictícios |
| D | Reconstrução ancorada no último pacote, recuando 1 s (`timestamp_est`) *(implementada só para EDA)* | Mais plausível que C | Ainda é estimativa; assume 1 Hz sem perdas |
| E | Corrigir na origem: `ts` (epoch via SNTP) e contador `seq` no payload do ESP32 | Elimina o problema; mede latência e perda real | Reflash, campos opcionais no schema, nova coleta |

### 4.5. Decisão adotada e encaminhamento
* **Semana 6 (implementado):** alternativa **B**, que é o padrão do pipeline. A coluna `timestamp_est` (alternativa **D**) é gerada com a flag `is_timestamp_estimated` e serve **apenas** à análise exploratória, **nunca** ao treinamento.
* **A IA pode prosseguir antes da alteração do firmware.** O *Isolation Forest* da Semana 7 pode usar atributos instantâneos (`rpm`, `temperature`, `speed`, `rpm_per_speed`), independentes do timestamp. `acceleration_ms2`/`rpm_delta` entram só nas linhas com `derivative_valid`, ou como atributos opcionais. Como o pipeline é determinístico, uma nova coleta com timestamp de origem exige apenas trocar a fonte do tempo e retreinar, o que é uma nova iteração do ciclo CRISP-DM (*Entendimento dos Dados → nova coleta*).
* **Alternativa E (sessão de hardware separada, fora do escopo do Executor 6):** a mudança é pequena. Envolve SNTP após o Wi-Fi, dois campos no `snprintf` e um contador estático. Pontos de atenção:
  1. O payload agrega o **último valor** de cada PID (`telemetry_set_*`). Um `ts` único no instante da publicação já elimina o atraso de rede; a hora exata de cada leitura CAN exigiria um timestamp por PID.
  2. Sem SNTP sincronizado o `ts` é inválido, e o backend deve recorrer ao horário de chegada.
  3. Campos `ts`/`seq` **opcionais** no Pydantic mantêm compatibilidade com os 2074 registros atuais e com o firmware antigo.
  4. `seq` permite medir objetivamente a perda de pacotes MQTT.

---

## 5. Resultados da EDA sobre os Dados Reais (`scripts/run_eda.py`)

### 5.1. Data Quality Report
| Métrica | Valor |
| :--- | :---: |
| Registros brutos → limpos | 2074 → **2073** |
| Removido: velocidade sentinela 255 km/h | 1 |
| Demais regras (timestamp, duplicatas, ausentes, faixas físicas) | 0 |
| Rajadas 4G mantidas (derivadas anuladas) | 177 |
| Quedas longas de sinal (derivadas anuladas) | 24 |
| Amostras com derivadas confiáveis | 1871 (90,3 %) |

### 5.2. Regimes Operacionais
| Regime | Amostras | Participação |
| :--- | :---: | :---: |
| Em movimento (`driving`) | 1231 | 59,38 % |
| Marcha lenta (`idle`) | 818 | 39,46 % |
| Motor desligado (`engine_off`) | 24 | 1,16 % |

### 5.3. Matriz de Correlação (Pearson)
|  | RPM | Temperatura | Velocidade | Aceleração |
| :--- | :---: | :---: | :---: | :---: |
| **RPM** | 1,000 | −0,634 | **0,820** | 0,161 |
| **Temperatura** | −0,634 | 1,000 | −0,716 | 0,048 |
| **Velocidade** | 0,820 | −0,716 | 1,000 | 0,052 |
| **Aceleração** | 0,161 | 0,048 | 0,052 | 1,000 |

Leitura: RPM e velocidade são fortemente correlacionados, como se espera numa transmissão mecânica. A correlação negativa da temperatura com velocidade/RPM é coerente com o maior fluxo de ar no radiador em movimento: a mediana é **88 °C em marcha lenta** contra **85 °C rodando**. Ainda assim, ela deve ser interpretada com cautela, porque há só um trajeto com o motor já aquecido (83–92 °C).

### 5.4. Limiares Normais Preliminares (faixa P05–P95; alerta P99)
| Escopo | Variável | P05 | Mediana | P95 | P99 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Marcha lenta | RPM | 935 | 952 | 1131 | 1305 |
| Marcha lenta | Temperatura (°C) | 86 | 88 | 89 | 90 |
| Em movimento | RPM | 948 | 2290 | 3527 | 3986 |
| Em movimento | Temperatura (°C) | 84 | 85 | 87 | 88 |
| Em movimento | Velocidade (km/h) | 5 | 33 | 56 | 64 |
| Em movimento | Aceleração (m/s²) | −0,83 | 0,00 | 1,08 | 2,21 |
| Em movimento | RPM/Velocidade | 42,1 | 63,8 | 193,0 | 235,9 |

> **Observações:** (i) o máximo de aceleração (6,29 m/s²) e o mínimo (−4,74 m/s²) são fisicamente improváveis para o veículo e indicam valores defasados em torno de oscilações de rede. Ficam abaixo do teto de 15 m/s² herdado do frontend e são candidatos naturais a "anomalias de dado" na Semana 7. (ii) Os limiares descrevem **um único trajeto** e são preliminares; novas coletas (motor frio, rodovia, trânsito) ampliarão a representatividade.

---

## 6. Validação e Testes Automatizados

* **`venv\Scripts\pytest.exe --ignore=backend/tests/test_main.py`** (sandbox): **24/24 aprovados**.
  * [test_data_preparation.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_data_preparation.py) (**11 novos**): outliers (`255 km/h`, `rpm < 0`, `rpm > 8000`, temperatura, velocidade, duplicatas), ordenação `[timestamp, id]`, rajadas `< 0,25 s` e quedas longas, `rpm_per_speed`, regimes, `timestamp_est` (normal e comprimido), SQLite ausente/existente/sem tabela, correlação 4×4 simétrica, percentis/limiares, DataFrame vazio, CLI `--export-clean` e renderização de `views/eda.py` no `AppTest`.
  * [test_frontend_and_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_frontend_and_e2e.py): 10 testes **sem alteração**, inclusive a renderização das 4 páginas.
  * [test_mqtt.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_mqtt.py): 3 testes.
* **`venv\Scripts\pytest.exe backend/tests/test_main.py`**: travou na sandbox (comportamento documentado em [run-python-tests.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/.gemini/rules/run-python-tests.md)); executado fora dela com **4/4 aprovados**.
* **Total: 28/28 testes aprovados.**
* **`venv\Scripts\ruff.exe check .`**: código de saída `0`.
* **Execução real:** `venv\Scripts\python.exe scripts\run_eda.py` sobre `vehicle_data.db`, com os resultados da Seção 5.

### Como reproduzir
```powershell
venv\Scripts\python.exe scripts\run_eda.py                  # auditoria no terminal
venv\Scripts\python.exe scripts\run_eda.py --export-clean   # + CSV em data/clean/ (gitignored)
```

---

## 7. Próximos Passos (Semana 7)
1. Instalar `scikit-learn` e treinar o *Isolation Forest* sobre `prepare_dataset(load_telemetry_from_sqlite())`, priorizando atributos independentes do timestamp e segmentando ou incluindo o regime.
2. Usar os limiares da Seção 5.4 como referência de validação dos *scores*.
3. (Opcional, trilha de hardware) Alternativa E: `ts` + `seq` no payload do ESP32 e nova coleta.
