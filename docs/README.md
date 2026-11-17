# 📚 Documentação e Relatoria Técnica de Engenharia

Bem-vindo ao diretório central de documentação e relatoria técnica do projeto **Central de Análise Veicular Preditiva (IoT)** — Trabalho de Conclusão de Curso (TCC) em Engenharia da Computação.

Este diretório atua como o ponto focal de governança de software, reunindo relatórios detalhados da evolução do código, decisões arquiteturais por marco de desenvolvimento (Pull Requests) e fundamentos acadêmico-normativos para a banca examinadora.

---

## 📑 Relatoria de Evolução do Código por Commit (Pull Requests)

Cada commit realizado no repositório foi decomposto e formalizado em um relatório técnico dedicado, documentando os objetivos alcançados, alterações estruturais de código, decisões de arquitetura e procedimentos de validação:

| PR # | Commit | Mensagem do Commit | Fase / Marco | Documento Detalhado |
| :---: | :---: | :--- | :---: | :--- |
| **PR #00** | `6b5083d` | `Initial commit` | Fundação | [pr_00_initial_commit.md](relatorios_dev/pr_00_initial_commit.md) |
| **PR #01** | `eba1297` | `teste` | Spike Exploratório | [pr_01_teste_arduino_poc.md](relatorios_dev/pr_01_teste_arduino_poc.md) |
| **PR #02** | `303c4d7` | `update teste` | Documentação | [pr_02_update_teste.md](relatorios_dev/pr_02_update_teste.md) |
| **PR #03** | `68ef50a` | `epic(fase1): add webpage, bd local e mockcar templates` | Fase 1 — Semana 1 | [pr_03_fase1_semana1_esteira_mock_first.md](relatorios_dev/pr_03_fase1_semana1_esteira_mock_first.md) |
| **PR #04** | `795d0dd` | `(alpha 1): add mqtts transmission, config file (no magic variable)` | Fase 1 — Semana 2 | [pr_04_fase1_semana2_ingestao_mqtts_config.md](relatorios_dev/pr_04_fase1_semana2_ingestao_mqtts_config.md) |
| **PR #05** | `c084227` | `(alpha 2): firmware esp-idf PIDs active reading from OBDII ISO 15765-4` | Fase 2 — Semana 3 | [pr_05_fase2_semana3_firmware_espidf_twai_can.md](relatorios_dev/pr_05_fase2_semana3_firmware_espidf_twai_can.md) |
| **PR #06** | `fca65d1` | `(docs): add relatorios sobre estruturacao de código` | Governança | [pr_06_docs_relatorios_arquitetura.md](relatorios_dev/pr_06_docs_relatorios_arquitetura.md) |
| **PR #07** | `c59b8e0` | `(alpha 2): MQTTS implementation on ESP32 with PIDs data` | Fase 2 — Semana 4 | [pr_07_fase2_semana4_firmware_cba_mqtts.md](relatorios_dev/pr_07_fase2_semana4_firmware_cba_mqtts.md) |
| **PR #08** | `124d3fe` | `(alpha 2): e2e verify script, field guide and CAN bus-off auto-recovery` | Fase 2 — Semana 5 | [pr_08_fase2_semana5_integracao_e2e_veiculo_real.md](relatorios_dev/pr_08_fase2_semana5_integracao_e2e_veiculo_real.md) |
| **PR #09** | `3636da2` | `(feat): add temporal telemetry API, modular sidebar frontend and phase 3/4 views` | Preparação Fases 3–4 | [pr_09_preparacao_fases3_4_frontend_historico_ia.md](relatorios_dev/pr_09_preparacao_fases3_4_frontend_historico_ia.md) |

---

## 🏛️ Relatórios Setoriais de Arquitetura por Módulo

Além da relatoria histórica por commit, os módulos possuem relatórios de fundamentação técnica profunda em suas respectivas pastas:

* **[Relatório de Arquitetura de Software Backend](../backend/docs/relatorio_arquitetura_backend.md):**  
  Detalhamento da ingestão de mensageria telemática via MQTTS (porta 8883 / TLS v1.2), validação estrita de fronteira com Pydantic v2, persistência transacional ACID com SQLAlchemy/SQLite, exposição via FastAPI RESTful e modelagem de ameaças (*Threat Modeling*, Zero Trust e controle de acesso via ACLs segundo NIST SP 800-207 e ISO/IEC 27001).
* **[Relatório de Arquitetura de Software Embarcado (Firmware ESP-IDF & CMake)](../hardware/docs/relatorio_arquitetura_firmware_cmake.md):**  
  Modelagem de Arquitetura Baseada em Componentes (CBA / ISO/IEC/IEEE 42010), mecânica do sistema de meta-build com CMake e Ninja, gerenciamento de memória thread-safe com FreeRTOS Mutex, temporizadores assíncronos não-bloqueantes para o barramento CAN/TWAI a 500 kbaud e sinalização em hardware (D13, D14, D26).
* **[Guia Operacional de Validação em Campo (Semana 5)](guia_validacao_campo.md):**  
  Checklist prático para coleta embarcada no VW Polo Track (Hotspot 4G, pinagem OBD-II, LEDs D13/D14/D26 e auditoria pós-rodagem).

---

## 🗺️ Mapa de Evolução e Próximas Etapas do Projeto

1. **Fase 1 (Semanas 1 e 2) — Concluída:** Esteira de dados completa (FastAPI + Pydantic + SQLite + MQTTS TLS 8883 + Streamlit + Mock).
2. **Fase 2 (Semanas 3, 4 e 5) — Concluída:** Firmware modular em C no ESP-IDF com leitura CAN TWAI a 500 kbaud + auto-recuperação de *Bus-Off*, transmissão telemática MQTTS, cálculo de aceleração instantânea ($\Delta v / \Delta t$), auditoria E2E em veículo real e dashboard modularizado.
3. **Fase 3 (Semanas 6 e 7) — Próxima Entrega:** Análise exploratória e limpeza de dados (EDA / CRISP-DM) com Pandas e modelagem preditiva com Scikit-Learn (*Isolation Forest*) para detecção de anomalias veiculares.
4. **Fase 4 (Semana 8) — Finalização:** Implantação do modelo preditivo no backend e congelamento de código (*Code Freeze*).
