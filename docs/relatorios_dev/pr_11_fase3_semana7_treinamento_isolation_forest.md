# Pull Request #11: Fase 3 (Semana 7) — CRISP-DM: Modelagem e Avaliação Determinística com Isolation Forest e Geração do Artefato `.pkl`

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Modelagem Não Supervisionada com Scikit-Learn (`IsolationForest`), Avaliação CRISP-DM e Serialização `.pkl`  
**Commit Associado:** *pendente* (alterações locais sobre `615d35d`)  
**Data:** 18 de Novembro de 2026  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`

---

## 1. Resumo Executivo e Objetivos

Este marco executa a **Semana 7 da Fase 3 (IA Preditiva Clássica)**, contemplando as fases de **Modelagem** e **Avaliação** da metodologia CRISP-DM sobre o conjunto real de telemetria coletado no VW Polo Track (`vehicle_data.db`, 16/11/2026) e preparado pelo pipeline determinístico da Semana 6 ([PR #10](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/relatorios_dev/pr_10_fase3_semana6_crispdm_limpeza_eda.md)).

Foi projetado e treinado um pipeline Scikit-Learn composto por `RobustScaler(quantile_range=(5.0, 95.0))` e `IsolationForest(n_estimators=200, contamination=0.02, random_state=42)`, acoplado a uma camada de atenuação monotônica fora do envelope observado de treino (`feature_bounds`) e serializado no artefato `backend/ml/isolation_forest_model.pkl` para implantação no backend e dashboard durante a **Semana 8**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  PIPELINE CRISP-DM — SEMANA 7 (MODELAGEM + AVALIAÇÃO)                  │
└────────────────────────────────────────────────────────────────────────────────────────┘

  [ vehicle_data.db ] ──► backend/ml/data_preparation.py :: prepare_dataset(include_estimated_timestamp=False)
                            │  (2074 brutos → 2073 limpos; 177 rajadas 4G preservadas)
                            ▼
                  backend/ml/anomaly_model.py
                    1. filter_active_engine       (exclui regime == "engine_off": 24 linhas → 2049 ativas)
                    2. build_feature_matrix       (7 atributos sem NaN; piso físico 5 km/h em rpm_per_speed)
                    3. build_anomaly_pipeline     (RobustScaler[P05–P95] + IsolationForest[200, 2 %, seed=42])
                    4. predict_anomalies          (decision_function − penalidade fora do envelope [min, max])
                    5. evaluate_anomaly_model     (trajeto real + 12 anomalias sintéticas físicas)
                    6. save_model_artifact        (serialização pickle HIGHEST_PROTOCOL + metadados/limiares)
                            │                                       │
                            ▼                                       ▼
             [ scripts/train_model.py ]            [ backend/ml/isolation_forest_model.pkl ]
             Relatório CRISP-DM no terminal        Artefato pronto para FastAPI / Streamlit (Semana 8)
```

### Objetivos Alcançados
1. **Dependência e Configuração:** instalação e fixação de `scikit-learn==1.9.1` em [requirements.txt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/requirements.txt) e definição de `ANOMALY_MODEL_PATH` em [backend/config.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/config.py).
2. **Módulo de Modelagem e Inferência ([backend/ml/anomaly_model.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/ml/anomaly_model.py)):** filtragem de motor em funcionamento (`regime != "engine_off"`), extração determinística de 7 atributos sem descarte de amostras de marcha lenta ou rajadas 4G, pipeline `RobustScaler` + `IsolationForest` e correção de saturação de fronteira para excursões severas fora do domínio de treino.
3. **Avaliação CRISP-DM Dupla (Real + Sintética):** identificação das 41 amostras mais atípicas do trajeto real (`2,00 %` das 2.049 amostras com motor ligado) e validação física com **100 % de detecção (12/12)** sobre anomalias sintéticas de superaquecimento (`> 108 °C`), sobre-rotação em marcha lenta e relação `rpm/speed` incoerente.
4. **CLI e Artefato `.pkl` ([scripts/train_model.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/train_model.py)):** geração e verificação do arquivo `backend/ml/isolation_forest_model.pkl` contendo o pipeline, colunas, fronteiras de atributos (`feature_bounds`), limiares normais da EDA (`normal_thresholds`) e resumo da validação.

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Descrição Técnica |
| :--- | :---: | :--- |
| [requirements.txt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/requirements.txt) | Modificado | Adição de `scikit-learn==1.9.1`. |
| [backend/config.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/config.py) | Modificado | Constante `ANOMALY_MODEL_PATH = BASE_DIR / "backend" / "ml" / "isolation_forest_model.pkl"`. |
| [backend/ml/\_\_init\_\_.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/ml/__init__.py) | Modificado | Atualização da documentação do pacote cobrindo Semanas 6 e 7. |
| [backend/ml/anomaly_model.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/ml/anomaly_model.py) | Criado | `AnomalyModelArtifact`, `filter_active_engine`, `build_feature_matrix`, `build_anomaly_pipeline`, `train_anomaly_model`, `predict_anomalies`, `generate_synthetic_anomalies`, `evaluate_anomaly_model`, `save_model_artifact`, `load_model_artifact`. |
| `backend/ml/isolation_forest_model.pkl` | Criado | Artefato binário treinado sobre as 2.049 amostras ativas do `vehicle_data.db`. |
| [scripts/train_model.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/train_model.py) | Criado | CLI de treinamento, relatório CRISP-DM no terminal e persistência do `.pkl`. |
| [backend/tests/test_anomaly_model.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_anomaly_model.py) | Criado | 5 testes unitários e de integração (atributos sem `NaN`, determinismo `random_state=42`, roundtrip `.pkl`, anomalias sintéticas vs. normais e CLI). |
| [docs/relatorios_dev/pr_10_fase3_semana6_crispdm_limpeza_eda.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/relatorios_dev/pr_10_fase3_semana6_crispdm_limpeza_eda.md) | Modificado | Registro do hash `615d35d`. |
| [docs/README.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/README.md) | Modificado | Atualização do hash `615d35d` no PR #10 e inclusão do PR #11. |

Arquivos **não** alterados (fronteira de escopo): `docs/latex/TCC_II/`, `hardware/`, `frontend/`, `backend/main.py`, `backend/mqtt_client.py`, `backend/database.py`, `backend/schemas/`.

---

## 3. Detalhamento Técnico da Modelagem

### 3.1. Seleção e Imputação Determinística de Atributos (`FEATURE_COLUMNS`)
O treinamento utiliza exclusivamente registros com o motor em operação (`regime != "engine_off"`, ou seja, $\text{RPM} \ge 300$), evitando que amostras com ignição ligada e motor parado ($\text{RPM} = 0$) distorçam a distribuição de marcha lenta. A coluna `timestamp_est` (criada na Semana 6 apenas para visualização exploratória) é explicitamente desativada via `prepare_dataset(..., include_estimated_timestamp=False)`.

| # | Atributo | Origem | Tratamento de Ausentes (`NaN`) / Justificativa Física |
| :-: | :--- | :--- | :--- |
| 1 | `rpm` | Instantâneo (PID `0x0C`) | Obrigatório na limpeza (`0.0` por segurança). |
| 2 | `temperature` | Instantâneo (PID `0x05`) | Obrigatório na limpeza (`0.0` por segurança). |
| 3 | `speed` | Instantâneo (PID `0x0D`) | Preenchido com `0.0` quando nulo. |
| 4 | `rpm_per_speed` | Engenharia (Semana 6) | Em `speed <= 5 km/h` (onde a EDA define `NaN`), imputado continuamente como $\text{rpm} / \max(\text{speed}, 5{,}0)$. Mantém marcha lenta normal ($\approx 950 / 5 = 190$) dentro da faixa de 1ª marcha e expõe sobre-rotações parado ($3600\text{–}5800 / 5 = 720\text{–}1160$). |
| 5 | `is_driving` | Regime Operacional | `1.0` se `regime == "driving"`, `0.0` caso contrário. Contextualiza o acoplamento rotação–velocidade. |
| 6 | `acceleration_ms2` | Derivada temporal | Mantida quando `derivative_valid == True`; preenchida com `0.0` em rajadas 4G (`dt < 0,25 s`) e quedas longas (`dt > 2,5 s`), preservando 100 % das leituras. |
| 7 | `rpm_delta` | Derivada temporal | Mantida quando `derivative_valid == True`; preenchida com `0.0` em rajadas 4G e quedas longas. |

### 3.2. Escalonamento P05–P95 e Saturação de Fronteira em Árvores de Isolamento
Durante a análise de distribuição dos 2.049 registros ativos do `vehicle_data.db`, identificaram-se duas propriedades matemáticas relevantes para a seção de *Modelagem e Avaliação* da monografia:
1. **Degenerescência do IQR (25 %–75 %) em variáveis derivadas com alta proporção de marcha lenta:** como `39,9 %` das amostras ativas pertencem ao regime `idle` ($\text{velocidade} = 0$) e `9,7 %` são rajadas/quedas com derivada anulada, o intervalo interquartil padrão (Q25–Q75) de `acceleration_ms2` é `0,00 m/s²` e o de `rpm_delta` é apenas `10,0 RPM`, ao passo que a faixa operacional `P05–P95` é `1,18 m/s²` e `403,8 RPM`. Por essa razão, o `RobustScaler` foi configurado com `quantile_range=(5.0, 95.0)`, alinhado aos limiares normais preliminares definidos na Semana 6.
2. **Saturação de corte além do envelope de treino em `IsolationTree`:** no algoritmo *Isolation Forest*, cada nó interno sorteia seu limiar de corte uniformemente dentro do intervalo $[\min(X_{\text{nó}, j}), \max(X_{\text{nó}, j})]$ observado no treino. Como o trajeto real ocorreu com o motor já aquecido e termostato estabilizado (`83–92 °C`, quantizado em inteiros de `1 °C` pelo PID `0x05`), nenhum nó das 200 árvores possui limiar de corte acima de `92 °C`. Consequentemente, uma árvore de decisão isolada trata `125 °C` de forma idêntica a `92 °C`. Para garantir monotonicidade física fora do domínio observado sem alterar nenhuma predição dentro da caixa de treino, `predict_anomalies()` subtrai do `decision_function(X)` uma penalidade proporcional ao excesso além de $[\min_j, \max_j]$ normalizado pela escala `P05–P95` (`feature_bounds`, com banda morta de `0,20`). Para 100 % das amostras dentro do domínio de treino, a penalidade é estritamente `0,0`.

---

## 4. Resultados Reais do Treinamento e Avaliação (`scripts/train_model.py`)

### 4.1. Resumo do Conjunto de Treinamento (`vehicle_data.db`)
| Métrica | Valor |
| :--- | :---: |
| Registros brutos → limpos | 2074 → **2073** |
| Registros `engine_off` excluídos do treino (e ignorados na inferência) | 24 |
| Registros com motor em operação usados no treino | **2049** |
| Hiperparâmetros do `IsolationForest` | `n_estimators=200`, `contamination=0.02`, `random_state=42` |
| Anomalias detectadas no trajeto real | **41 (2,00 %)** |
| Quantis do `anomaly_score` no treino | $\min = -0{,}1162$ · $P_{01} = -0{,}0198$ · $P_{05} = 0{,}0442$ · $P_{50} = 0{,}1657$ · $P_{95} = 0{,}2304$ · $\max = 0{,}2312$ |

### 4.2. Distribuição de Anomalias por Regime Operacional
| Regime | Amostras | Anomalias Detectadas | Taxa no Regime | Score Mínimo | Score Mediano ($P_{50}$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Marcha lenta (`idle`) | 818 | 7 | 0,86 % | −0,1162 | 0,2139 |
| Em movimento (`driving`) | 1231 | 34 | 2,76 % | −0,1059 | 0,1404 |

### 4.3. Top 10 Anomalias Detectadas no Trajeto Real
| ID | Horário (UTC) | Regime | RPM | Temp (°C) | Vel (km/h) | RPM/Vel | Acel (m/s²) | ΔRPM | Score | Interpretação Física |
| :-: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 500 | 18:32:21.590 | `idle` | 2583 | 88 | 0 | — *(516,6)* | 0,000 | +1930 | **−0,116** | Aceleração brusca em vazio com veículo parado |
| 557 | 18:33:19.105 | `driving` | 3475 | 87 | 25 | 139,0 | **+6,108** | +1853 | **−0,106** | Pico de aceleração (defasagem de rede prevista no PR #10) |
| 194 | 18:27:12.586 | `driving` | 3524 | 88 | 12 | 293,7 | 0,000 | +2000 | **−0,100** | Esticada de 1ª marcha em baixa velocidade |
| 57 | 18:24:54.257 | `driving` | 3713 | 88 | 15 | 247,5 | 0,000 | +1443 | **−0,077** | Alta rotação em 1ª marcha (acima do P99 de `rpm_per_speed`) |
| 54 | 18:24:51.255 | `driving` | 2270 | 88 | 6 | **378,3** | 0,000 | +1147 | **−0,074** | Maior razão `rpm/speed` de todo o trajeto (arrancada) |
| 277 | 18:28:36.384 | `driving` | 2195 | 87 | 4 | — *(439,0)* | 0,000 | +1523 | **−0,069** | Saída da imobilidade com salto rápido de rotação |
| 633 | 18:34:35.853 | `driving` | 3383 | 87 | 19 | 178,1 | +1,638 | +1924 | **−0,064** | Retomada forte em marcha baixa |
| 1222 | 21:06:12.208 | `idle` | 1239 | **92** | 0 | — *(247,8)* | 0,000 | +1239 | **−0,062** | Partida a quente no teto térmico do dataset (92 °C) |
| 120 | 18:25:57.863 | `driving` | 1222 | 85 | 18 | 67,9 | **−3,370** | −1663 | **−0,062** | Frenagem e queda brusca de rotação |
| 691 | 18:36:07.685 | `driving` | 3095 | 87 | 17 | 182,1 | +1,810 | **+2351** | **−0,058** | Maior salto positivo de RPM ($\Delta\text{RPM} = +2351$) |

### 4.4. Validação com Anomalias Sintéticas Físicas
Para validar a capacidade de generalização em cenários críticos de falha não presentes no trajeto normal de coleta, 12 amostras sintéticas distribuídas em três modos de falha foram submetidas ao modelo:

| Categoria | Descrição Física | Amostras | Detectadas | Taxa de Detecção | Score Médio | Score Mínimo |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `overheating` | Superaquecimento (`112–126 °C`, $> 108\ ^\circ\text{C}$) | 4 | 4 | **100,0 %** | −0,5795 | −0,8460 |
| `idle_overrev` | Sobre-rotação em marcha lenta (`3600–5800 RPM` a `0–1 km/h`) | 4 | 4 | **100,0 %** | −0,2830 | −0,4564 |
| `gear_mismatch` | Relação `rpm/speed` incoerente (`4900–5600 RPM` a `10–14 km/h` e `950 RPM` a `115 km/h`) | 4 | 4 | **100,0 %** | −0,0673 | −0,0991 |
| **Total Global** | **Bateria sintética de validação física** | **12** | **12** | **100,0 %** | **−0,3099** | **−0,8460** |

---

## 5. Validação e Testes Automatizados

* **`venv\Scripts\pytest.exe --ignore=backend/tests/test_main.py`** (sandbox): **29/29 aprovados**.
  * [test_anomaly_model.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_anomaly_model.py) (**5 novos**): extração de atributos sem `NaN` com marcha lenta e rajadas 4G + filtragem de `engine_off`, reprodutibilidade determinística (`random_state=42`), persistência e leitura do `.pkl` em `tmp_path`, discriminação entre sondas normais (`is_anomaly == False`) e anomalias sintéticas físicas (`100 %` detectadas) e execução completa da CLI `scripts/train_model.py`.
  * [test_data_preparation.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_data_preparation.py): 11 testes aprovados.
  * [test_frontend_and_e2e.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_frontend_and_e2e.py): 10 testes aprovados.
  * [test_mqtt.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_mqtt.py): 3 testes aprovados.
* **`venv\Scripts\pytest.exe backend/tests/test_main.py`** (executado fora da sandbox no Windows): **4/4 aprovados**.
* **Total geral da suíte: 33/33 testes aprovados.**
* **`venv\Scripts\ruff.exe check .`**: código de saída `0` (`All checks passed!`).
* **Artefato gerado:** `backend/ml/isolation_forest_model.pkl` confirmado em disco via `venv\Scripts\python.exe scripts\train_model.py`.

### Como reproduzir
```powershell
venv\Scripts\python.exe scripts\train_model.py
venv\Scripts\python.exe scripts\train_model.py --contamination 0.02 --top-k 10
```

---

## 6. Próximos Passos (Semana 8 — Fase 4: Implantação e Code Freeze)
1. Carregar `backend/ml/isolation_forest_model.pkl` via `load_model_artifact()` no backend FastAPI e expor a inferência/alertas de anomalia.
2. Integrar os resultados reais do modelo treinado (`is_anomaly`, `anomaly_score` e diagnósticos) na página `🤖 Diagnóstico Preditivo (IA)` (`frontend/views/ai_diagnostics.py`).
3. Executar a bateria final de testes E2E e realizar o congelamento de código (*Code Freeze*).
