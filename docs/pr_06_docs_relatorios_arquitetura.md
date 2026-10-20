# Pull Request #06: Governança de Engenharia — Relatórios Técnicos Formais de Arquitetura de Software

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Documentação Técnica, Engenharia de Software e Fundamentação Normativa  
**Commit Associado:** [`fca65d1225df75c0952b38d461e9dfe76037da6b`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `fca65d1`)  
**Data:** 20 de Outubro de 2026 às 09:42:32 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Com o avanço das fases práticas de implementação do sistema, fez-se imperativo formalizar e documentar a fundamentação teórica, metodológica e normativa de todo o ecossistema de software desenvolvido. Este compromisso atende ao rigor acadêmico exigido para a monografia e para a banca examinadora do Trabalho de Conclusão de Curso (TCC) em Engenharia da Computação.

Este marco incorporou relatórios extensos e profundos dedicados aos dois subsistemas centrais da aplicação: o **Subsistema de Backend e Ingestão Telemática** e o **Subsistema de Firmware Embarcado e Sistema de Build CMake**.

---

## 2. Arquivos Criados

| Arquivo | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| [backend/docs/relatorio_arquitetura_backend.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/docs/relatorio_arquitetura_backend.md) | Criado | +289 / -0 | Relatório formal sobre arquitetura em camadas, ingestão MQTTS, modelo Pub/Sub, The Twelve-Factor App, cibersegurança e normas ISO/IEC/NIST. |
| [hardware/docs/relatorio_arquitetura_firmware_cmake.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/docs/relatorio_arquitetura_firmware_cmake.md) | Criado | +184 / -0 | Relatório formal sobre Component-Based Architecture (CBA), sistema de build CMake/Ninja no ESP-IDF, diretrizes MISRA-C e concorrência segura. |

---

## 3. Síntese do Conteúdo Técnico Formalizado

### 3.1. Relatório de Arquitetura de Software Backend
O documento [relatorio_arquitetura_backend.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/docs/relatorio_arquitetura_backend.md) fundamenta a construção da esteira de dados em princípios canônicos da computação distribuída:
1. **Arquitetura em Camadas (Layered Architecture — Fowler, 2002):**  
   Particionamento horizontal estrito entre ingestão de mensagens (`mqtt_client.py`), validação de fronteira (`schemas/telemetry.py`), persistência transacional (`database.py`) e exposição RESTful (`main.py`).
2. **The Twelve-Factor App (Wiggins, 2011):**  
   Aplicação do Fator III (Configurações centralizadas via SSOT em `config.py`), Fator IV (serviços de apoio acoplados) e Fator IX (descartabilidade e inicialização não-bloqueante com `lifespan`).
3. **Mecânica do Protocolo OASIS MQTT v3.1.1 / ISO/IEC 20922:2016:**  
   Detalhamento da regra canônica das seções 4.7.1.1 e 4.7.2:
   * Wildcards (`+` e `#`) são restritos à subscrição (`SUBSCRIBE`), habilitando o backend a atuar como concentrador *multi-tenant* via `ls-praxedes/scanner-obd2/+`.
   * Publicações (`PUBLISH`) devem utilizar caixas postais unívocas e concretas (`ls-praxedes/scanner-obd2/qsr5c99`), evitando desconexões instantâneas pelo broker.
4. **Cibersegurança e Modelagem de Ameaças (Threat Modeling):**  
   Análise de trânsito seguro via **TLS v1.2 / RFC 5246** e diretrizes de defesa em profundidade baseadas no **NIST SP 800-207 (Zero Trust Architecture)** e na norma **ISO/IEC 27001**, detalhando o controle de acesso por listas **ACL** para impedir visualização não autorizada de telemetria em brokers corporativos.

### 3.2. Relatório de Arquitetura de Firmware Embarcado
O documento [relatorio_arquitetura_firmware_cmake.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/hardware/docs/relatorio_arquitetura_firmware_cmake.md) fundamenta a transição de código para o nível industrial automotivo:
1. **Arquitetura Baseada em Componentes (CBA — ISO/IEC/IEEE 42010:2011):**  
   Decomposição do firmware em subsistemas autocontidos e fracamente acoplados (`telemetry`, `obd2_can`, `wifi_manager`, `mqtt_service`), expostos unicamente por interfaces de cabeçalho (`.h`).
2. **Mecânica do Sistema de Build CMake / Ninja no ESP-IDF:**  
   Explicação do grafo de dependências, da macro de registro `idf_component_register`, da conversão de binários em símbolos de link-edição via `EMBED_TXTFILES` e da geração do arquivo final `obd2_scanner.bin`.
3. **Diretrizes MISRA-C:2012 e Barr Group Embedded C Coding Standard:**  
   Erradicação de variáveis globais públicas desprotegidas e uso mandatório de semáforos de exclusão mútua (**FreeRTOS Mutex**) para assegurar a consistência de dados entre tarefas concorrentes.
4. **Matriz Comparativa Monólito vs. Modular:**  
   Avaliação objetiva de impacto técnico comprovando a redução de tempo de compilação incremental, facilidade de manutenção e aumento de testabilidade.

---

## 4. Relevância Acadêmica e para a Banca Examinadora

* **Rigor Metodológico:** O projeto afasta-se de abordagens meramente empíricas (*hobbyist proof-of-concept*) e ancora-se em normas técnicas consolidadas (ISO/IEC, IETF, NIST, SAE).
* **Base Teórica para a Monografia:** Os relatórios servem como capítulos técnicos completos prontos para incorporação no documento final do TCC.
