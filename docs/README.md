# 📚 Documentação e Relatoria Técnica de Engenharia

Bem-vindo ao diretório central de documentação e relatoria técnica do projeto **Central de Análise Veicular Preditiva (IoT)** — Trabalho de Conclusão de Curso (TCC) em Engenharia da Computação.

Este diretório atua como o ponto focal de governança de software, reunindo relatórios detalhados da evolução do código, decisões arquiteturais por marco de desenvolvimento (Pull Requests) e fundamentos acadêmico-normativos para a banca examinadora.

---

## 📑 Relatoria de Evolução do Código por Commit (Pull Requests)

Cada commit realizado no repositório foi decomposto e formalizado em um relatório técnico dedicado, documentando os objetivos alcançados, alterações estruturais de código, decisões de arquitetura e procedimentos de validação:

| PR # | Commit | Mensagem do Commit | Fase / Marco | Documento Detalhado |
| :---: | :---: | :--- | :---: | :--- |
| **PR #00** | `6b5083d` | `Initial commit` | Fundação | [pr_00_initial_commit.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_00_initial_commit.md) |
| **PR #01** | `eba1297` | `teste` | Spike Exploratório | [pr_01_teste_arduino_poc.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_01_teste_arduino_poc.md) |
| **PR #02** | `303c4d7` | `update teste` | Documentação | [pr_02_update_teste.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_02_update_teste.md) |
| **PR #03** | `68ef50a` | `epic(fase1): add webpage, bd local e mockcar templates` | Fase 1 — Semana 1 | [pr_03_fase1_semana1_esteira_mock_first.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_03_fase1_semana1_esteira_mock_first.md) |
| **PR #04** | `795d0dd` | `(alpha 1): add mqtts transmission, config file (no magic variable)` | Fase 1 — Semana 2 | [pr_04_fase1_semana2_ingestao_mqtts_config.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_04_fase1_semana2_ingestao_mqtts_config.md) |
| **PR #05** | `c084227` | `(alpha 2): firmware esp-idf PIDs active reading from OBDII ISO 15765-4` | Fase 2 — Semana 3 | [pr_05_fase2_semana3_firmware_espidf_twai_can.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_05_fase2_semana3_firmware_espidf_twai_can.md) |
| **PR #06** | `fca65d1` | `(docs): add relatorios sobre estruturacao de código` | Governança | [pr_06_docs_relatorios_arquitetura.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_06_docs_relatorios_arquitetura.md) |
| **PR #07** | `c59b8e0` | `(alpha 2): MQTTS implementation on ESP32 with PIDs data` | Fase 2 — Semana 4 | [pr_07_fase2_semana4_firmware_cba_mqtts.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docs/pr_07_fase2_semana4_firmware_cba_mqtts.md) |

---

## 🏛️ Relatórios Setoriais de Arquitetura por Módulo

Além da relatoria histórica por commit, os módulos possuem relatórios de fundamentação técnica profunda em suas respectivas pastas:

* **[Relatório de Arquitetura de Software Backend](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/docs/relatorio_arquitetura_backend.md):**  
  Detalhamento da ingestão de mensageria telemática via MQTTS (porta 8883 / TLS v1.2), validação estrita de fronteira com Pydantic v2, persistência transacional ACID com SQLAlchemy/SQLite, exposição via FastAPI RESTful e modelagem de ameaças (*Threat Modeling*, Zero Trust e controle de acesso via ACLs segundo NIST SP 800-207 e ISO/IEC 27001).
* **[Relatório de Arquitetura de Software Embarcado (Firmware ESP-IDF & CMake)](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/docs/relatorio_arquitetura_firmware_cmake.md):**  
  Modelagem de Arquitetura Baseada em Componentes (CBA / ISO/IEC/IEEE 42010), mecânica do sistema de meta-build com CMake e Ninja, gerenciamento de memória thread-safe com FreeRTOS Mutex, temporizadores assíncronos não-bloqueantes para o barramento CAN/TWAI a 500 kbaud e sinalização em hardware (D13, D14, D26).

---

## 🗺️ Mapa de Evolução e Próximas Etapas do Projeto

1. **Fase 1 (Semanas 1 e 2) — Concluída:** Esteira de dados completa (FastAPI + Pydantic + SQLite + MQTTS TLS 8883 + Streamlit + Mock).
2. **Fase 2 (Semanas 3 e 4) — Concluída:** Firmware modular em C no ESP-IDF com leitura CAN TWAI ISO 15765-4 a 500 kbaud e transmissão telemática MQTTS com certificado X.509 embutido.
3. **Fase 2 (Semana 5) — Próxima Entrega:** Integração E2E no veículo físico real, cálculo de aceleração instantânea ($\Delta v / \Delta t$) e status de conexão no dashboard Streamlit.
4. **Fase 3 (Semanas 6 e 7) — Em Sequência:** Análise exploratória de dados (EDA) com Pandas e modelagem preditiva com Scikit-Learn (*Isolation Forest*) para detecção de anomalias veiculares.
5. **Fase 4 (Semana 8) — Finalização:** Implantação do modelo preditivo no backend e congelamento de código (*Code Freeze*).
