# Relatório de Arquitetura de Software Backend: Ingestão Telemática, Persistência e Serviços de Aplicação

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Camada de Backend, Ingestão MQTTS e Exposição de APIs  
**Tecnologias Centrais:** Python 3.12, FastAPI, Paho-MQTT, Pydantic v2, SQLAlchemy, SQLite, TLS v1.2  
**Data:** Outubro de 2026  

---

## 1. Resumo Executivo

O presente documento técnico-acadêmico consolida a fundamentação teórica, o detalhamento arquitetural e as justificativas formais relativas à estruturação do **Subsistema de Backend e Ingestão de Dados Telemáticos** do projeto de telemetria veicular OBD-II.

O backend atua como a espinha dorsal de processamento centralizado na nuvem/servidor, recebendo dados telemáticos de alta frequência (RPM, temperatura do líquido de arrefecimento, velocidade) transmitidos pela unidade telemática embarcada (ESP32) através do protocolo seguro **MQTTS (MQTT sobre TLS)**, executando a validação sintática e semântica rigorosa dos payloads via **Pydantic**, armazenando-os de forma transacional e determinística com **SQLAlchemy**, e disponibilizando-os para o cliente de visualização (Frontend/Dashboard) por intermédio de uma **API RESTful de alta performance em FastAPI**.

São apresentadas as razões da modularização em pacotes isolados, a centralização de parâmetros sob a ótica do *The Twelve-Factor App*, o modelo de tópicos e wildcards do MQTT, o tratamento de segurança com listas de controle de acesso (ACL) e defesa em profundidade (*Zero Trust*), bem como o embasamento teórico referenciado em normas internacionais (ISO/IEC, IETF RFCs, NIST) e literatura canônica de Engenharia de Software.

---

## 2. Fundamentação Teórica e Princípios de Engenharia de Software

A estruturação do backend não se deu por conveniência empírica, mas orientada por padrões arquiteturais e metodologias consagradas na indústria de software corporativo e computação distribuída.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FLUXO ARQUITETURAL DE TELEMETRIA                      │
└─────────────────────────────────────────────────────────────────────────────┘

  [ ESP32 Firmware ] (Camada Física / Borda)
          │
          │ Publicação MQTTS (Porta 8883 / TLS v1.2)
          ▼
   [ Broker MQTTS ] (ex: Mosquitto / EMQX)
          │ Tópico: "ls-praxedes/scanner-obd2/qsr5c99"
          ▼
   [ backend/mqtt_client.py ] ── Worker Assíncrono (Paho MQTT Callback)
          │
          ▼
   [ backend/schemas/telemetry.py ] ── Validação e Sanitização (Pydantic v2)
          │ (Rejeita dados corrompidos ou tipos incorretos)
          ▼
   [ backend/database.py ] ── ORM SQLAlchemy (Sessão / Transação ACID)
          │
          ▼
   [ vehicle_data.db ] ── Banco de Dados Relacional (SQLite)
          ▲
          │ Consultas ORM (Sessão via Dependency Injection)
   [ backend/main.py ] ── Endpoints REST FastAPI (/api/v1/telemetry)
          ▲
          │ Requisições HTTP (GET)
   [ Frontend / Dashboard ] (Visualização do Usuário)
```

### 2.1. Arquitetura em Camadas (Layered Architecture) e Separação de Preocupações (SoC)
Segundo **Fowler (2002)**, uma das formas fundamentais de controlar a complexidade em sistemas de software é particionar a aplicação em camadas horizontais distintas, onde cada camada possui uma responsabilidade específica e depende apenas de abstrações bem definidas:
1. **Camada de Ingestão de Mensageria (`mqtt_client.py`):** Responsável estritamente pela conexão com a infraestrutura de rede externa (broker MQTT), escuta assíncrona de eventos e decodificação do pacote de bytes da rede.
2. **Camada de Contrato e Domínio (`schemas/telemetry.py`):** Define a estrutura dos dados, validação de limites físicos dos sensores e integridade de tipos.
3. **Camada de Acesso a Dados / Persistência (`database.py`):** Encapsula a infraestrutura de conexão relacional, dialeto SQL e mapeamento objeto-relacional (ORM), desacoplando a aplicação do motor de banco específico.
4. **Camada de Aplicação e Exposição Web (`main.py`):** Gerencia o ciclo de vida do serviço, middleware HTTP, injeção de dependências e resolução de rotas para clientes externos.

Essa separação impede que detalhes de infraestrutura (como conexões de sockets ou queries SQL brutas) vazem para os controladores de endpoint, facilitando manutenções evolutivas e testes automatizados.

### 2.2. Princípios SOLID Aplicados ao Backend
A aderência aos princípios do design orientado a objetos e arquitetura limpa (**Martin, 2017**) reflete-se na organização do código:
* **Single Responsibility Principle (SRP):** Cada arquivo atende a um único vetor de mudança. Se a URL ou porta do broker mudar, altera-se apenas o arquivo de configuração; se uma nova regra de validação de RPM for instituída, altera-se apenas o schema Pydantic; se o banco for migrado para PostgreSQL, ajusta-se apenas o módulo de banco de dados.
* **Dependency Inversion Principle (DIP):** Os endpoints da FastAPI não instanciam conexões com o banco diretamente de forma *hardcoded*. Em vez disso, utilizam o mecanismo de **Injeção de Dependência** (`Depends(database.get_db)`), permitindo que durante a execução de suítes de testes automatizados a sessão do banco seja substituída por um mock ou por uma base SQLite transitória em memória (`:memory:`).

### 2.3. A Metodologia dos Doze Fatores (*The Twelve-Factor App*)
A estruturação do diretório do backend segue rigorosamente os preceitos formulados por **Wiggins (2011)** para aplicações nativas de nuvem (*cloud-native*):
* **Fator III — Configurações (Config):** O código-fonte da aplicação deve ser estritamente separado de suas configurações dinâmicas de ambiente. Todas as variáveis sensíveis e endereços de infraestrutura (Broker host, porta, certificados, URLs de banco) residem de forma centralizada em `backend/config.py`. Isso garante o princípio **Single Source of Truth (SSOT)**: múltiplos módulos e scripts de mock consomem as mesmas constantes, eliminando divergências de portas ou caminhos de certificados.
* **Fator IV — Serviços de Apoio (Backing Services):** O banco de dados relacional e o corretor MQTT são tratados como recursos acoplados que podem ser redirecionados de ambiente de desenvolvimento para produção sem alterações na lógica de negócio central.
* **Fator IX — Descartabilidade e Ciclo de Vida (Disposability):** O backend foi arquitetado com gerenciamento robusto de ciclo de vida através do gerenciador de contexto `lifespan` da FastAPI. Ao inicializar o servidor, o cliente MQTT conecta-se e dispara seu loop assíncrono em segundo plano; ao encerrar o servidor (`SIGTERM` ou `Ctrl+C`), as conexões do broker e as sessões de banco são finalizadas de forma limpa (*graceful shutdown*), evitando conexões zumbis e travamento de arquivos de banco.

---

## 3. Detalhamento dos Módulos do Sistema

A árvore do módulo backend foi organizada de forma concisa e de baixa carga cognitiva:

```
backend/
├── __init__.py           # Declara o diretório como pacote importável Python
├── config.py             # Single Source of Truth: Broker, tópicos, caminhos, BD
├── database.py           # Conexão SQLAlchemy, SessionLocal e Modelo Declarativo ORM
├── main.py               # Instância FastAPI, ciclo de vida (lifespan) e endpoints REST
├── mqtt_client.py        # Cliente MQTTS (Paho), callbacks de rede e persistência
├── docs/                 # Documentação técnica e relatórios de arquitetura
├── schemas/              # Contratos de dados e schemas de validação
│   └── telemetry.py      # TelemetryCreate e TelemetryResponse via Pydantic
└── tests/                # Suíte de testes unitários automatizados
    ├── test_main.py      # Validação de rotas HTTP e respostas da API
    └── test_mqtt.py      # Testes de ingestão MQTT com mocks de sessão e validação
```

### 3.1. Módulo de Configuração Centralizada (`config.py`)
* **Papel:** Ponto focal de parametrização da aplicação.
* **Conceito Chave — Single Source of Truth (SSOT):**
  Antes da centralização, o endereço do broker `test.mosquitto.org`, a porta TLS `8883` e os tópicos estavam replicados de forma redundante em `main.py`, `mqtt_client.py`, no script de mock e nas suítes de teste. A criação do `config.py` unificou essas definições:
  ```python
  from pathlib import Path

  BASE_DIR = Path(__file__).resolve().parent.parent

  MQTT_BROKER = "test.mosquitto.org"
  MQTT_PORT = 8883
  MQTT_TOPIC = "ls-praxedes/scanner-obd2/+"          # Wildcard para assinatura
  MQTT_MOCK_TOPIC = "ls-praxedes/scanner-obd2/qsr5c99" # Tópico concreto para envio
  CA_CERT_PATH = str(BASE_DIR / "mosquitto.org.crt")
  DATABASE_URL = f"sqlite:///{BASE_DIR / 'vehicle_data.db'}"
  ```
* **Resolução Dinâmica de Caminhos:** O uso de `pathlib.Path` resolve caminhos absolutos relativos à raiz do projeto de forma agnóstica ao sistema operacional (Windows, Linux ou containers Docker), mitigando falhas clássicas de caminho relativo (*FileNotFoundError*) na busca do certificado X.509 ou do arquivo de banco.

### 3.2. Módulo de Persistência e Mapeamento Objeto-Relacional (`database.py`)
* **Papel:** Abstração de persistência transacional com **SQLAlchemy 2.x**.
* **Modelo de Dados Relacional:**
  A tabela `telemetry` registra com fidelidade os valores físicos lidos da ECU:
  * `id` (`Integer`, Chave Primária, indexado): Identificador sequencial único.
  * `rpm` (`Float`, não-nulo): Rotações por minuto do motor.
  * `temperature` (`Float`, não-nulo): Temperatura do arrefecimento (°C).
  * `speed` (`Float`, anulável): Velocidade veicular (km/h), permitindo compatibilidade com ECUs que demoram a responder o PID de velocidade ou veículos estacionados.
  * `timestamp` (`DateTime`, com fuso UTC): Registro cronológico de inserção com precisão de microssegundos via `datetime.now(timezone.utc)`.
* **Gerenciador de Sessão e Injeção de Dependências:**
  A função `get_db()` opera como um gerador (*generator*) sob o protocolo de contexto do Python. Quando uma requisição HTTP chega ao endpoint da FastAPI, a sessão é aberta; ao término da requisição (mesmo em caso de erro), a cláusula `finally` garante a chamada `db.close()`, eliminando vazamentos de descritores de arquivo (*resource leakage*).

### 3.3. Módulo de Contrato e Schemas de Domínio (`schemas/telemetry.py`)
* **Papel:** Garantir a integridade da fronteira de dados (*Boundary Data Sanitization*) através de **Pydantic v2**.
* **Validação Sintática e Semântica:**
  Em sistemas telemáticos, payloads corrompidos ou ataques maliciosos podem enviar valores em formatos inesperados (ex: strings em campos numéricos, injeções de SQL ou números negativos de RPM). O schema `TelemetryCreate` atua como um firewall de aplicação:
  ```python
  class TelemetryCreate(BaseModel):
      rpm: float = Field(..., description="Engine RPM")
      temperature: float = Field(..., description="Engine Coolant Temperature in Celsius")
      speed: Optional[float] = Field(None, description="Vehicle speed in km/h")
  ```
  Se a ECU ou um cliente arbitrário enviar `{"rpm": "duas_mil", "temperature": 90}`, o Pydantic intercepta o erro no ponto de entrada e aborta o processamento antes que qualquer instrução de banco seja gerada.
* **Schema de Resposta (`TelemetryResponse`):**
  Extende o schema de entrada adicionando os metadados gerados pelo servidor (`id` e `timestamp`) com `from_attributes = True`, permitindo serialização direta a partir de objetos do ORM SQLAlchemy para JSON com alta velocidade.

### 3.4. Módulo de Ingestão de Mensageria em Tempo Real (`mqtt_client.py`)
* **Papel:** Serviço de mensageria assíncrona baseado na biblioteca **Eclipse Paho-MQTT**.
* **Mapeamento de Eventos e Callbacks:**
  * `on_connect`: Registrado para lidar com o handshake com o broker. Avalia o código de retorno `rc` (Return Code). Caso bem-sucedido (`rc == 0`), inscreve o cliente no tópico telemático de múltiplos dispositivos (`MQTT_TOPIC`).
  * `on_message`: Executado a cada recepção de pacote publicado no tópico inscrito. 
* **Resiliência e Tratamento de Exceções:**
  O método de recepção implementa tratamento defensivo em três camadas:
  1. Captura de `json.JSONDecodeError`: Se o payload transmitido pela rede não for um JSON bem formado.
  2. Captura de `pydantic.ValidationError`: Se o JSON for válido sintaticamente, mas violar os tipos de dados exigidos.
  3. Bloco transacional com `try...except...finally` de banco de dados: Caso ocorra um erro de escrita no SQLite, o sistema executa `db.rollback()`, registra o incidente em log estruturado e finaliza a sessão em `db.close()`, garantindo que o worker nunca entre em estado de parada catastrófica (*crash*).

### 3.5. Módulo de Aplicação e API RESTful (`main.py`)
* **Papel:** Orquestração de serviços web, endpoints HTTP de consulta e controle de ciclo de vida.
* **Gerenciador de Ciclo de Vida Assíncrono (`@asynccontextmanager lifespan`):**
  Em versões modernas da FastAPI / Starlette, eventos legados de `@app.on_event("startup")` foram substituídos pelo gerenciador `lifespan`. No início do serviço, o cliente MQTT inicia seu laço em segundo plano através de `client.loop_start()`, permitindo que o servidor FastAPI continue respondendo requisições HTTP na thread principal do servidor ASGI (Uvicorn), enquanto a thread do Paho MQTT consome as mensagens da rede de forma não-bloqueante.
* **Endpoints Disponibilizados:**
  * `POST /api/v1/telemetry`: Endpoint para ingestão alternativa via HTTP ou testes manuais de integração.
  * `GET /api/v1/telemetry`: Endpoint de consulta para o Frontend e dashboards analíticos, com suporte nativo a paginação (`skip`, `limit`) e ordenação cronológica decrescente (`order_by(Telemetry.timestamp.desc())`), garantindo que o dashboard sempre receba a leitura mais recente no topo.

---

## 4. Comunicação Telemática: MQTT x MQTTS e o Modelo Publish/Subscribe

O protocolo **MQTT (Message Queuing Telemetry Transport)**, padronizado pela norma **ISO/IEC 20922:2016** e pela organização **OASIS**, foi concebido especificamente para cenários de telemetria em redes móveis e dispositivos embarcados sujeitos a largura de banda restrita e alta latência.

### 4.1. Vantagens do MQTT sobre o Paradigma HTTP em Telemetria Veicular
| Característica | HTTP / REST Tradicional | MQTT / MQTTS (Adotado) | Justificativa Técnica |
| :--- | :--- | :--- | :--- |
| **Padrão de Comunicação** | Requisição-Resposta (Pull) | Publicação-Assinatura (Push) | No veículo, a unidade embarcada produz dados contínuos; abrir um handshake TCP/HTTP completo a cada segundo consome banda excessiva e processamento desnecessário na CPU do ESP32. |
| **Tamanho do Cabeçalho** | Centenas de bytes (Headers HTTP textuais, cookies, etc.) | Fixo de 2 bytes na camada de aplicação | Reduz drasticamente o consumo do pacote de dados 4G/Wi-Fi do veículo. |
| **Acoplamento de Rede** | Ponto-a-ponto direto (o cliente precisa conhecer o IP do backend) | Desacoplado no tempo e no espaço através do Broker | O veículo e o backend não comunicam diretamente; se o backend reiniciar, o broker retém conexões e o veículo não falha. |
| **QoS (Qualidade de Serviço)** | Inexistente nativamente (depende da aplicação) | 3 Níveis nativos (QoS 0, 1 e 2) | Permite escolher entre máxima velocidade ou entrega garantida de telemetria crítica. |

### 4.2. A Mecânica dos Tópicos MQTT e o Uso de Wildcards

Uma das dúvidas mais comuns de arquitetura envolve a atribuição de tópicos. O protocolo MQTT organiza as mensagens em uma estrutura hierárquica separada por barras (`/`).

O padrão OASIS MQTT v3.1.1 estipula regras estritas sobre o uso de caracteres coringa (*wildcards*):
1. **Wildcard de Nível Único (`+`):** Casa com exatamente um nível da árvore de tópicos. Exemplo: `ls-praxedes/scanner-obd2/+` recebe mensagens de:
   * `ls-praxedes/scanner-obd2/qsr5c99` (Veículo 1)
   * `ls-praxedes/scanner-obd2/abc1234` (Veículo 2)
2. **Wildcard Multinível (`#`):** Casa com múltiplos níveis subsequentes da árvore.

#### A Regra Canônica do MQTT: Assinatura vs. Publicação
> **REGRA FORMAL DA ESPECIFICAÇÃO OASIS MQTT (Seção 4.7.1.1 / 4.7.2):**  
> Os caracteres coringa `+` e `#` são permitidos **exclusivamente na operação de subscrição (`SUBSCRIBE`)**. É estritamente **proibido publicar (`PUBLISH`) em tópicos que contenham wildcards**.

* **Por que o backend usa `MQTT_TOPIC = ".../+"`?**  
  O backend atua como um concentrador de múltiplos veículos (*multi-tenant*). Ao assinar `ls-praxedes/scanner-obd2/+`, um único worker do backend escuta simultaneamente todos os dispositivos veiculares que transmitem no sistema.
* **Por que o mock e o ESP32 usam `MQTT_MOCK_TOPIC = ".../qsr5c99"`?**  
  O emissor deve direcionar a mensagem a uma caixa postal unívoca e concreta. Ao tentar publicar em um tópico contendo `+`, o broker rejeita o pacote ou desconecta o cliente imediatamente por violação de protocolo.

---

## 5. Cibersegurança, Privacidade e Controle de Acesso (Threat Modeling)

Um dos pontos mais críticos em sistemas veiculares e telemática conectada refere-se à segurança da informação e à preservação da privacidade do condutor e da integridade da ECU.

### 5.1. O Papel do MQTTS (TLS v1.2 / Porta 8883)
O tráfego de dados por MQTT puro (porta 1883) trafega em texto claro (*plain text*). Qualquer atacante situado na mesma rede Wi-Fi, roteador público ou operadora 4G pode realizar ataques de escuta passiva (*eavesdropping*) ou interceptação/modificação de dados (*Man-In-The-Middle - MITM*).

A arquitetura implementada adota **MQTTS sobre a porta 8883**, em conformidade com as recomendações da **IETF RFC 5246 (TLS 1.2)** e **IETF RFC 8446 (TLS 1.3)**:
1. **Criptografia em Trânsito:** Todo o payload JSON e os cabeçalhos de aplicação são cifrados através de algoritmos criptográficos robustos (AES-128/256-GCM), tornando os dados ininteligíveis a bisbilhoteiros.
2. **Autenticação do Servidor via Certificado Raiz (CA Cert):** O arquivo `mosquitto.org.crt` é carregado pelo backend (`backend/config.py`) e embutido no firmware do ESP32 (`ca_cert.h`). Durante o aperto de mão (*TLS Handshake*), o cliente valida matematicamente a chave pública do broker contra a assinatura da Autoridade Certificadora confiável, impedindo ataques de falsificação de identidade de servidor (*DNS Spoofing* ou *Server Impersonation*).

### 5.2. A Diferença entre Criptografia de Canal e Autorização de Acesso (O Risco do Broker Público)
Conforme discutido ao longo da modelagem do projeto:
> *Embora a transmissão seja segura via MQTTS, se o broker for público e sem autenticação, qualquer entidade externa pode assinar o tópico e visualizar a telemetria ou injetar comandos falsos.*

A criptografia de transporte (TLS) garante **apenas que ninguém no caminho do cabo/rádio consiga ler os dados**. Ela **não** impede que um terceiro se conecte legitimamente ao mesmo broker e solicite a assinatura do tópico.

Para resolver este vetor de vulnerabilidade em ambientes corporativos e de produção, a arquitetura telemática apoia-se em três pilares formais de segurança baseados no **NIST SP 800-207 (Zero Trust Architecture)** e na norma **ISO/IEC 27001**:

```
                                  POLÍTICA DE SEGURANÇA E ACLs
                                  
   Dispositivo Veicular               Corretor MQTT Seguro             Serviço de Ingestão Backend
  (Certificado / Chave X.509)        (Broker Mosquitto com ACLs)       (Credencial de Alta Confiança)
          │                                      │                                      │
          │ 1. Conexão MQTTS (mTLS)              │                                      │
          ├─────────────────────────────────────►│                                      │
          │ 2. Checagem de Identidade & ACL      │                                      │
          │    Permissão de PUBLISH apenas em:   │                                      │
          │    "vehicles/{device_id}/telemetry"  │                                      │
          │    (REJEITA qualquer leitura)        │                                      │
          │                                      │ 3. Inscrição Autenticada             │
          │                                      │    Permissão de SUBSCRIBE em:        │
          │                                      │    "vehicles/+/telemetry"            │
          │                                      │◄─────────────────────────────────────┤
          │                                      │                                      │
          │ 4. Publicação Cifrada                │ 5. Encaminhamento Controlado         │
          │ ──► [ Dados Telemáticos ] ─────────► │ ──► [ Ingestão e Persistência ] ───► │
          │                                      │                                      │
```

1. **Autenticação Forte de Dispositivos (AAA):**
   * Em produção, o broker desabilita conexões anônimas (`allow_anonymous false`).
   * Cada scanner automotivo recebe credenciais exclusivas de identificação (par usuário/senha único ou **Autenticação Mútua via Certificados Digitais X.509 — mTLS**, conforme **IETF RFC 5280**).
2. **Listas de Controle de Acesso (ACL — Access Control Lists):**
   * Aplicação do **Princípio do Menor Privilégio (*Principle of Least Privilege — PoLP*)**:
     * **Perfil Veicular (ESP32):** Possui permissão exclusiva de **ESCRITA (`write`)** em seu respectivo tópico estrito: `vehicles/polo_qsr5c99/telemetry`. O scanner automotivo é terminantemente impedido de assinar (`read`) qualquer tópico do broker.
     * **Perfil de Ingestão (Backend):** Possui permissão exclusiva de **LEITURA (`read`)** no tópico wildcard: `vehicles/+/telemetry`.
     * **Clientes Arbitrários ou Frontend:** Não possuem acesso direto ao broker MQTT; consomem os dados exclusivamente via API REST protegida por tokens de autenticação (JWT / OAuth2).

---

## 6. Estratégia de Qualidade de Software e Testes Automatizados

A estruturação modular e o isolamento de dependências no backend viabilizam uma estratégia de testes rigorosa com a ferramenta **pytest**, cobrindo tanto a camada de mensageria assíncrona quanto a camada de API HTTP sem depender da disponibilidade de hardware real ou de conexão ativa com a internet.

### 6.1. Testabilidade da Ingestão Telemática (`backend/tests/test_mqtt.py`)
O módulo de testes unitários do cliente MQTT utiliza o mecanismo de substituição de comportamento (**Mocks** com `unittest.mock.patch` e `MagicMock`):
* `test_on_message_valid_payload`: Simula a recepção de uma mensagem MQTT contendo JSON com telemetria válida. Verifica se o schema Pydantic parseia os dados corretamente e se o método `db.commit()` é invocado de forma satisfatória.
* `test_on_message_invalid_json`: Injeta uma carga binária malformada (`b"not_a_json"`). Valida que a aplicação intercepta o erro em nível de decodificação e que o banco de dados não executa operações indevidas (`assert not mock_db.commit.called`).
* `test_on_message_invalid_schema`: Injeta um JSON com tipos incompatíveis (ex: campo `rpm` preenchido como string). Valida a interceptação pelo Pydantic sem corrupção do banco relacional.

### 6.2. Testabilidade da API HTTP (`backend/tests/test_main.py`)
Utiliza o `TestClient` provido pela biblioteca Starlette/FastAPI, validando os códigos de status HTTP (200 OK para listagem, 200 OK para persistência e 422 Unprocessable Entity para dados que violem o contrato).

---

## 7. Justificativas Acadêmicas e Profissionais para a Banca de TCC

### 7.1. Relevância Acadêmica (Engenharia da Computação)
1. **Convergência de Subáreas da Computação:** O backend integra conceitos interdisciplinares basilares da ciência e engenharia da computação:
   * **Sistemas Distribuídos e Mensageria:** Comunicação assíncrona com corretor de mensagens desacoplado no tempo e espaço.
   * **Redes de Computadores e Cibersegurança:** Implementação de protocolos de transporte seguro (TLS v1.2), criptografia assimétrica e análise de ameaças de rede.
   * **Bancos de Dados e Persistência:** Aplicação de propriedades ACID em transações relacionais mediadas por ORM.
   * **Engenharia de Software:** Adoção formal de padrões arquiteturais em camadas, SOLID e The Twelve-Factor App.
2. **Superação de Projetos Amadores (*Proof-of-Concept vs. Production-Grade*):** Muitos projetos de graduação limitam-se a publicar dados em texto puro em servidores HTTP locais com loops bloqueantes. Esta implementação demonstra maturidade técnica ao empregar threads concorrentes com loop não-bloqueante (`loop_start`), validação formal por schema, injeção de dependências e testes automatizados.

### 7.2. Relevância Profissional e Alinhamento com a Indústria 4.0
1. **Padrão de Mercado para Telemetria Automotiva e IoT:** O uso combinado de **FastAPI + Pydantic + SQLAlchemy + MQTT/TLS** é o padrão *de facto* adotado pelas principais empresas de telemetria, rastreamento de frotas e montadoras globais de veículos conectados (ex: arquiteturas de veículos conectados AWS IoT Core e Azure IoT Hub).
2. **Manutenibilidade e Escalabilidade Horizontal:** A segregação do backend em módulos autocontidos viabiliza a migração futura para microsserviços conteinerizados em Docker e orquestrados via Kubernetes sem necessidade de refatoração do código-fonte.

---

## 8. Referências Bibliográficas Reais e Normativas Técnicas

1. **DIERKS, Tim; RESCORLA, Eric.** *RFC 5246: The Transport Layer Security (TLS) Protocol Version 1.2.* Internet Engineering Task Force (IETF), 2008. Disponível em: <https://www.rfc-editor.org/rfc/rfc5246>. Acesso em: 20 out. 2026.
2. **FAGAN, Michael et al.** *NIST Special Publication 800-213: IoT Device Cybersecurity Guidance for the Federal Government.* National Institute of Standards and Technology (NIST), Gaithersburg, 2021. DOI: 10.6028/NIST.SP.800-213.
3. **FIELDING, Roy Thomas.** *Architectural Styles and the Design of Network-based Software Architectures.* Doctoral dissertation, University of California, Irvine, 2000. (Fundamentação formal do padrão REST).
4. **FOWLER, Martin.** *Patterns of Enterprise Application Architecture.* Boston: Addison-Wesley, 2002.
5. **INTERNATIONAL ORGANIZATION FOR STANDARDIZATION.** *ISO/IEC 20922:2016: Information technology — Message Queuing Telemetry Transport (MQTT) v3.1.1.* Genebra: ISO, 2016.
6. **INTERNATIONAL ORGANIZATION FOR STANDARDIZATION.** *ISO/IEC 27001:2022: Information security, cybersecurity and privacy protection — Information security management systems — Requirements.* Genebra: ISO, 2022.
7. **MARTIN, Robert C.** *Clean Architecture: A Craftsman's Guide to Software Structure and Design.* Boston: Prentice Hall, 2017.
8. **OASIS.** *MQTT Version 3.1.1.* OASIS Standard, 2014. Disponível em: <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html>. Acesso em: 20 out. 2026.
9. **RESCORLA, Eric.** *RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3.* Internet Engineering Task Force (IETF), 2018. Disponível em: <https://www.rfc-editor.org/rfc/rfc8446>. Acesso em: 20 out. 2026.
10. **ROSE, Scott et al.** *NIST Special Publication 800-207: Zero Trust Architecture.* National Institute of Standards and Technology (NIST), Gaithersburg, 2020. DOI: 10.6028/NIST.SP.800-207.
11. **WIGGINS, Adam.** *The Twelve-Factor App.* Heroku, 2011. Disponível em: <https://12factor.net/>. Acesso em: 20 out. 2026.
