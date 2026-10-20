# Pull Request #04: Fase 1 (Semana 2) — Transição para Mensageria MQTTS e Configuração Centralizada (Twelve-Factor)

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Ingestão Telemática, Cibersegurança e Configuração  
**Commit Associado:** [`795d0ddc85d96fc282423aba25add64b81a01a3c`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `795d0dd`)  
**Data:** 10 de Outubro de 2026 às 17:32:49 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Este marco representa a entrega dos objetivos da **Semana 2 (Fase 1)** do projeto, consolidando uma **mudança estrutural de paradigma de comunicação**: a transição do modelo síncrono cliente-servidor (HTTP POST) para a arquitetura assíncrona orientada a eventos por publicação e subscrição utilizando **MQTTS (MQTT sobre TLS na porta 8883)**.

Essa transformação prepara o subsistema de backend para receber fluxos contínuos de telemetria automotiva transmitidos por microcontroladores embarcados sob conexões móveis (4G/Wi-Fi). Adicionalmente, foi implementada a centralização formal de parâmetros de infraestrutura sob a metodologia **The Twelve-Factor App**.

### Objetivos do Marco
1. **Transição de Protocolo para MQTTS:** Adotar o protocolo **ISO/IEC 20922:2016 (MQTT v3.1.1)** cifrado com **TLS v1.2** na porta 8883, eliminando tráfego em texto plano.
2. **Eliminação de Variáveis Mágicas (SSOT):** Centralizar todas as variáveis de rede, caminhos de banco e certificados em `backend/config.py`, utilizando resolução dinâmica de caminhos (`pathlib.Path`).
3. **Worker de Ingestão Assíncrona:** Criar o serviço `backend/mqtt_client.py` baseado na biblioteca **Eclipse Paho-MQTT**, operando em segundo plano (`loop_start`).
4. **Ciclo de Vida Limpo (Lifespan):** Integrar o ciclo de vida do cliente MQTT ao servidor FastAPI por meio do gerenciador moderno `@asynccontextmanager lifespan`, garantindo inicialização ordenada e desligamento gracioso (*graceful shutdown*).
5. **Manutenção do Contrato de Validação:** Garantir que todo payload recebido do broker passe obrigatoriamente pela validação do Pydantic (`TelemetryCreate`) antes de alcançar o SQLite.
6. **Testabilidade com Mocks:** Desenvolver suíte de testes unitários automatizados para o worker MQTT isolando a conexão de rede com `unittest.mock`.
7. **Refatoração do Emulador e Broker Local:** Atualizar `scripts/mock_car.py` para despacho via MQTTS e disponibilizar `docker-compose.yml` para execução do Eclipse Mosquitto em contingência local.

```
┌────────────────────────────────────────────────────────────────────────┐
│               FLUXO DA ESTEIRA DE TELEMETRIA MQTTS (SEMANA 2)          │
└────────────────────────────────────────────────────────────────────────┘

 [ scripts/mock_car.py ] ── Publicação MQTTS (Porta 8883 / TLS v1.2)
            │ Tópico Concreto: "ls-praxedes/scanner-obd2/qsr5c99"
            ▼
    [ Broker Mosquitto ] (test.mosquitto.org:8883)
            │ Assinatura Wildcard: "ls-praxedes/scanner-obd2/+"
            ▼
 [ backend/mqtt_client.py ] ── Worker Paho-MQTT em Background Thread (loop_start)
            │
            ├─► Validação com Pydantic (TelemetryCreate)
            ├─► Abertura de Sessão Transacional SQLAlchemy
            └─► Commit / Rollback Seguro no SQLite (vehicle_data.db)
```

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| [backend/config.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/config.py) | Criado | +18 / -0 | Ponto focal de parametrização (SSOT): `MQTT_BROKER`, `MQTT_PORT = 8883`, `MQTT_TOPIC`, `MQTT_MOCK_TOPIC`, `CA_CERT_PATH`, `DATABASE_URL`. |
| [mosquitto.org.crt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/mosquitto.org.crt) | Criado | +24 / -0 | Certificado raiz público da autoridade certificadora do broker Mosquitto (formato PEM / X.509). |
| [backend/mqtt_client.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/mqtt_client.py) | Criado | +53 / -0 | Cliente Paho-MQTT com contexto SSL/TLS, callbacks de rede (`on_connect`, `on_message`) e persistência transacional com rollback defensivo. |
| [backend/main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/main.py) | Modificado | +24 / -1 | Integração do worker MQTT ao ciclo de vida da API via gerenciador `@asynccontextmanager lifespan(app)`. |
| [scripts/mock_car.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/mock_car.py) | Modificado | +52 / -16 | Refatoração integral do gerador veicular para despachar telemetria cifrada via MQTTS na porta 8883. |
| [backend/tests/test_mqtt.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_mqtt.py) | Criado | +72 / -0 | Testes unitários do worker MQTT simulando recepção de rede com mocks. |
| [backend/tests/test_main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_main.py) | Modificado | +9 / -1 | Adaptação dos testes de rotas para compatibilidade com o contexto assíncrono. |
| [docker-compose.yml](file:///c:/Users/lucas/Documents/OBDII%20Scanner/docker-compose.yml) | Criado | +14 / -0 | Definição de container Eclipse Mosquitto para execução isolada em ambiente local. |
| [requirements.txt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/requirements.txt) | Modificado | +1 / -0 | Adição da dependência `paho-mqtt`. |
| [frontend/app.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/app.py) | Modificado | +5 / -5 | Alinhamento da consulta e atualização contínua com os dados persistidos pelo MQTT. |
| [README.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/README.md) | Modificado | +12 / -12 | Atualização das diretrizes e instruções de inicialização do Broker Mosquitto. |

---

## 3. Detalhamento Técnico das Modificações

### 3.1. Centralização SSOT e Twelve-Factor App (`config.py`)
Em conformidade com o **Fator III (Configurações)** do manifesto *The Twelve-Factor App*, parâmetros operacionais foram unificados em uma única fonte de verdade:
```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 8883
MQTT_TOPIC = "ls-praxedes/scanner-obd2/+"          # Assinatura (Wildcard)
MQTT_MOCK_TOPIC = "ls-praxedes/scanner-obd2/qsr5c99" # Envio Concreto
CA_CERT_PATH = str(BASE_DIR / "mosquitto.org.crt")
DATABASE_URL = f"sqlite:///{BASE_DIR / 'vehicle_data.db'}"
```
* **Resolução Dinâmica:** O emprego de `pathlib.Path(__file__)` resolve caminhos absolutos no sistema operacional, extinguindo erros de caminho relativo (`FileNotFoundError`) ao carregar certificados ou conectar ao banco.

### 3.2. Worker MQTTS com Tratamento Defensivo (`mqtt_client.py`)
* **Pilha Criptográfica TLS:** Configuração do cliente com `ssl.PROTOCOL_TLS_CLIENT` e injeção do arquivo `mosquitto.org.crt` via `client.tls_set(ca_certs=CA_CERT_PATH)`.
* **Tratamento de Exceções em Três Camadas:**
  1. `json.JSONDecodeError`: Intercepta payloads binários ou corrompidos pela rede.
  2. `pydantic.ValidationError`: Bloqueia pacotes sintaticamente válidos mas com valores de campos incompatíveis.
  3. Bloco transacional com `try...except...finally` no SQLite: Caso ocorra erro de I/O em disco, executa `db.rollback()`, emite log estruturado e finaliza a sessão em `db.close()`, blindando o worker contra falhas fatais (*crashes*).

### 3.3. Ciclo de Vida Assíncrono (`main.py`)
* O uso de `@asynccontextmanager lifespan(app)` substitui handlers de startup obsoletos:
  * No boot do Uvicorn: executa `client.loop_start()`, iniciando a thread de segundo plano do Paho-MQTT para consumo contínuo de pacotes sem travar a thread ASGI principal.
  * No encerramento: invoca `client.loop_stop()` e `client.disconnect()`, garantindo o fechamento gracioso das conexões TCP e liberação dos descritores de sockets.

---

## 4. Decisões de Arquitetura e Engenharia de Software

1. **Aderência à Norma OASIS MQTT v3.1.1 (Seção 4.7):**
   * **Assinatura:** O backend subscreve o tópico usando o wildcard de nível único `ls-praxedes/scanner-obd2/+`, habilitando suporte *multi-tenant* (um único backend escuta simultaneamente múltiplos veículos).
   * **Publicação:** A especificação internacional proíbe expressamente publicar em tópicos contendo caracteres coringa. O emissor (`mock_car.py` e posteriormente o ESP32) publica estritamente em um tópico concreto (`ls-praxedes/scanner-obd2/qsr5c99`), evitando rejeição imediata do pacote pelo broker.
2. **Cibersegurança em Trânsito (TLS v1.2 / RFC 5246):**
   * Criptografia forte de ponta a ponta na porta 8883, mitigando ataques de escuta passiva (*eavesdropping*) ou alteração de dados veiculares em trânsito (*Man-In-The-Middle - MITM*).
3. **Eficiência de Rede em Cenários Veiculares:**
   * Comparado ao HTTP, o cabeçalho fixo do MQTT de apenas 2 bytes reduz drasticamente o consumo de banda de internet móvel (4G/Hotspot) do veículo.

---

## 5. Plano de Validação e Testes Automatizados

* **Bateria de Testes (`test_mqtt.py` com Mocks):**
  * `test_on_message_valid_payload`: Simula evento de rede com dados telemáticos válidos. Confirma a instanciação do schema Pydantic e a chamada transacional `db.commit()`.
  * `test_on_message_invalid_json`: Injeta bytes arbitrários malformados (`b"not_a_json"`). Valida a captura de erro e confirma que `db.commit()` não é executado.
  * `test_on_message_invalid_schema`: Injeta JSON com campos corrompidos (string no lugar de numérico). Valida o bloqueio pelo Pydantic sem poluição do banco.
* **Comando de Verificação:**
  ```powershell
  python -m pytest
  ```
  *Resultado: 6 testes unitários aprovados (3 de rotas HTTP e 3 de mensageria MQTTS).*
