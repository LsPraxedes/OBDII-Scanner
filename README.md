# 🚗 Central de Análise Veicular Preditiva (IoT)

![Status do Projeto](https://img.shields.io/badge/Status-Alpha_1-yellow)
![Hardware](https://img.shields.io/badge/Hardware-ESP32%20%7C%20CAN-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20MQTT-brightgreen)
![Frontend](https://img.shields.io/badge/Frontend-Streamlit-red)

Este repositório contém o código-fonte do Trabalho de Conclusão de Curso (TCC) em Engenharia da Computação, que propõe o desenvolvimento de um sistema computacional auxiliar para monitoramento, transmissão e análise preditiva de dados veiculares de um **VW Polo Track 2025 (adaptado para o protocolo ISO 15765-4 CAN a 500 kbaud)**[cite: 1, 2].

O objetivo é criar uma solução de baixo custo que atue como um computador de bordo inteligente, capaz não apenas de exibir dados em tempo real, mas de empregar Machine Learning (IA) para prever anomalias de comportamento do motor[cite: 1].

---

## 🏗️ Arquitetura do Sistema

O projeto utiliza uma abordagem Top-Down e uma arquitetura desacoplada (Hardware $\rightarrow$ Nuvem $\rightarrow$ Interface) [cite: 1], dividida nos seguintes módulos:

1. **Hardware (A Coleta):**
   - Microcontrolador **ESP32** programado em **C** utilizando o framework oficial nativo **ESP-IDF** [cite: 1].
   - Conexão à porta OBD-II do veículo utilizando um transceptor CAN (ex: SN65HVD230) [cite: 1, 2].
   - Leitura nativa de PIDs (ex: RPM, Temperatura) extraídos via protocolo CAN (ID de resposta `7E8` do ECM) [cite: 2].

2. **Comunicação (A Ponte):**
   - Transmissão dos pacotes de dados processados pelo ESP32 via Wi-Fi [cite: 1].
   - Envio dos pacotes JSON utilizando o protocolo **MQTT** para um Broker (ex: Eclipse Mosquitto) [cite: 1].

3. **Backend & Armazenamento (O Cérebro):**
   - Desenvolvido em **Python** utilizando **FastAPI** para alta performance assíncrona.
   - Cliente MQTT rodando em *background* (`paho-mqtt`) para capturar os tópicos de telemetria.
   - Validação estrita de integridade de payload JSON utilizando **Pydantic** para evitar ruídos.
   - Armazenamento de séries temporais em banco de dados relacional **SQLite** [cite: 1].

4. **Inteligência Artificial (A Predição):**
   - Implementada em **Python** utilizando **Scikit-Learn** e **Pandas**, guiada pela metodologia CRISP-DM [cite: 1].
   - Uso de modelos de Machine Learning Clássico (ex: *Isolation Forest*) para detecção de anomalias com base no histórico do banco de dados [cite: 1].

5. **Frontend (A Visualização):**
   - Dashboard web rápido e interativo construído em **Streamlit** (Python) para a exibição de gráficos históricos e alertas do modelo preditivo.

---

## 🗓️ Cronograma de Desenvolvimento (Fases)

O projeto está dividido em etapas de validação para mitigar riscos técnicos:

- **Fase 1 (Alpha 1):** Esteira de Dados (Setup FastAPI, Banco, MQTT e Dashboard Streamlit com dados mockados).
- **Fase 2 (Alpha 2):** Comunicação de Baixo Nível (Programação do barramento TWAI do ESP32 via ESP-IDF para leitura CAN E2E).
- **Fase 3 (Alpha 3):** Análise Preditiva (Tratamento de dados com Pandas e modelagem de Machine Learning com Scikit-Learn).
- **Fase 4: (Alpha 4)** Implantação e Integração (Plugar a IA no FastAPI para gerar alertas em tempo real no dashboard).
- **Fase 5: (Beta 1)** Validação final com testes em campo e formatação para entrega do TCC.
- **Fase 6: (Beta 2)** Testes por terceiros e desenvolvimento de mais funcionalidades e protocolos OBD2.
- ... (Fases posteriores serão definidas)

---

## 🚀 Como Iniciar (Setup do Ambiente)

### 1. Requisitos Prévios

- **Python 3.10+**
- **Docker** (Opcional, caso prefira rodar o Broker MQTT conteinerizado).
- **VS Code** com as extensões `ESP-IDF` e `Google Antigravity` (ou Antigravity IDE) instaladas.

### 2. Rodando o Ambiente Python (Nuvem/Visualização)

*O foco inicial (Fase 1) é o desenvolvimento da esteira de dados.*

```bash
# 1. Clone o repositório
git clone [https://github.com/lspraxedes/obdii-scanner.git](https://github.com/lspraxedes/obdii-scanner.git)
cd obdii-scanner

# 2. Crie e ative o ambiente virtual
python -m venv venv
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
