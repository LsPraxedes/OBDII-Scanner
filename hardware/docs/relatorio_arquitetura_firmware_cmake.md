# Relatório de Arquitetura de Software Embarcado: Estruturação Modular e Sistema de Build CMake no ESP-IDF

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Alvo de Hardware:** Espressif ESP32 (WROOM-32 DevKit V1)  
**Ambiente de Desenvolvimento:** ESP-IDF v6.1.0 / FreeRTOS / CMake / Ninja  
**Data:** Outubro de 2026  

---

## 1. Resumo Executivo

O presente documento apresenta a fundamentação teórica, a modelagem arquitetural e as justificativas técnico-científicas da transição do firmware da unidade telemática veicular de uma estrutura monolítica em arquivo único (`main.c`) para uma **Arquitetura Baseada em Componentes (Component-Based Architecture — CBA)** gerenciada pelo sistema de meta-build **CMake** no ecossistema **ESP-IDF**.

A solução implementada segrega as responsabilidades de baixo nível (barramento automotivo CAN/TWAI a 500 kbaud e transceptor físico), conectividade de rede (Wi-Fi Station com máquina de estados finita de reconexão), segurança telemática (cliente MQTTS sobre TLS v1.2 na porta 8883 com certificado raiz embutido e sinalização em GPIO 26) e gestão de dados thread-safe (telemetria concorrente com exclusão mútua), culminando em um orquestrador desacoplado no módulo `main`. 

---

## 2. Fundamentação Teórica e Princípios de Engenharia de Software

A estruturação adotada encontra respaldo em preceitos consolidados da Engenharia de Software e em normas para sistemas embarcados de missão crítica.

### 2.1. Arquitetura Baseada em Componentes (CBA) e Norma ISO/IEC/IEEE 42010
A norma **ISO/IEC/IEEE 42010:2011** (*Systems and software engineering — Architecture description*) estabelece que uma arquitetura de software deve ser organizada em visões que expressem o particionamento do sistema em subsistemas modulares com interfaces bem delineadas.

A abordagem **Component-Based Architecture (CBA)** preconiza que componentes de software sejam:
* **Autocontidos:** Cada componente encapsula dados, lógica interna e drivers específicos.
* **Componíveis:** As dependências são declaradas de forma explícita nas interfaces públicas (arquivos de cabeçalho `.h`).
* **Substituíveis:** Alterações internas no hardware de rede ou no protocolo de transporte não produzem efeitos colaterais na camada de leitura veicular.

### 2.2. Princípios SOLID Aplicados a C Embarcado
Embora desenvolvida em Linguagem C (paradigma estruturado), a arquitetura aplica conceitos fundamentais do design orientado a objetos:
1. **Single Responsibility Principle (SRP):** Cada módulo possui uma única razão para mudar. O `wifi_manager` lida exclusivamente com o enlace 802.11; o `obd2_can` lida apenas com a norma ISO 15765-4 / barramento CAN; o `mqtt_service` cuida do protocolo de telemetria; o `telemetry` gerencia o estado da memória compartilhada.
2. **Interface Segregation:** O orquestrador `main.c` enxerga apenas funções de inicialização de alto nível (`telemetry_init()`, `obd2_can_init()`, etc.), desconhecendo registradores internos, buffers estáticos ou ISRs do driver.

### 2.3. Diretrizes MISRA-C e Segurança Operacional
Segundo as diretrizes **MISRA C:2012** (*Motor Industry Software Reliability Association*) e o guia **Barr Group Embedded C Coding Standard**, sistemas automotivos devem evitar variáveis globais expostas e acoplamento temporal. Na arquitetura implementada:
* Não existem estruturas de dados globais públicas sem qualificador `static`.
* O acesso à telemetria entre tasks concorrentes é mediado por um semáforo de exclusão mútua (**Mutex** do FreeRTOS), prevenindo condições de corrida (*race conditions*) e leituras inconsistentes de memória (*dirty reads*).

---

## 3. Mecânica do Sistema de Build ESP-IDF com CMake

O ESP-IDF abandona sistemas legados de *Makefiles* manuais em prol do **CMake**, um sistema de meta-build que gera grafos de compilação otimizados para o motor **Ninja**.

```
                           hardware/esp32/
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
        hardware/esp32/main/        hardware/esp32/components/
                │                               │
           (main.c)             ┌───────────────┼───────────────┬───────────────┐
                                ▼               ▼               ▼               ▼
                            telemetry/      obd2_can/     wifi_manager/   mqtt_service/
                                │               │               │               │
                            (lib.a)          (lib.a)         (lib.a)         (lib.a)
                                └───────────────┼───────────────┴───────────────┘
                                                ▼
                                         LINKER (ld)
                                                ▼
                                        obd2_scanner.elf
                                                ▼
                                        obd2_scanner.bin (Flash)
```

### 3.1. Hierarquia de Arquivos `CMakeLists.txt`
1. **CMakeLists.txt Raiz (`hardware/esp32/CMakeLists.txt`):**
   * Ponto de entrada do CMake para o projeto.
   * Invoca `$ENV{IDF_PATH}/tools/cmake/project.cmake`, que carrega os scripts internos do ESP-IDF.
   * Registra o projeto via `project(obd2_scanner)`.
   * Realiza a descoberta automática (*auto-discovery*) dos componentes contidos na pasta `hardware/esp32/components/`.

2. **CMakeLists.txt dos Componentes (`components/<nome>/CMakeLists.txt`):**
   * Invoca a macro do framework: `idf_component_register(...)`.
   * Parâmetros configurados:
     * `SRCS`: Arquivos-fonte em C que serão compilados em código objeto (`.o`).
     * `INCLUDE_DIRS`: Diretórios com arquivos de cabeçalho (`include/`) expostos publicamente a outros módulos.
     * `REQUIRES`: Dependências públicas obrigatórias (outros componentes do ESP-IDF ou do projeto).
     * `EMBED_TXTFILES`: Instrução para converter arquivos binários/texto (ex: o certificado TLS `mosquitto.org.crt`) diretamente em símbolos de link-edição.

3. **CMakeLists.txt da Aplicação Principal (`main/CMakeLists.txt`):**
   * Registra `main.c` e declara as dependências de alto nível necessárias para compor a imagem de boot.

### 3.2. Ciclo de Compilação e Link-Edição
O fluxo de geração do firmware opera em quatro fases determinísticas:
1. **Varredura e Construção do Grafo de Dependências:** O CMake mapeia a árvore de inclusões e dependências entre componentes, garantindo que `telemetry` seja compilado antes de `mqtt_service` e `obd2_can`.
2. **Compilação Isolada das Unidades de Tradução:** O compilador cruzado `xtensa-esp32-elf-gcc` compila cada arquivo `.c` gerando arquivos `.o`.
3. **Criação de Bibliotecas Estáticas:** O utilitário `xtensa-esp32-elf-ar` agrupa os arquivos `.o` de cada componente em bibliotecas estáticas compactas (`libtelemetry.a`, `libobd2_can.a`, `libwifi_manager.a`, `libmqtt_service.a`).
4. **Link-Edição Final (`xtensa-esp32-elf-ld`):** O linker concatena as bibliotecas estáticas criadas com as bibliotecas do sistema (FreeRTOS, ROM, HAL, LwIP, mbedTLS) e resolve as tabelas de símbolos, produzindo o binário executável `obd2_scanner.elf`. O utilitário `esptool.py` sintetiza o arquivo final `obd2_scanner.bin`, pronto para gravação física na memória Flash.

---

## 4. Análise Comparativa: Monólito vs. Arquitetura Modular

| Métrica / Critério | Abordagem Monolítica (`main.c` único) | Arquitetura Modular (Componentes CMake) | Impacto Técnico e Operacional |
| :--- | :--- | :--- | :--- |
| **Linhas de Código por Arquivo** | > 540 linhas em arquivo único | ~30 a 130 linhas por módulo | Maior legibilidade, menor carga cognitiva e revisão de código facilitada. |
| **Tempo de Compilação Incremental** | Alto: qualquer ajuste recompila todo o código | Mínimo: o CMake recompila apenas o arquivo alterado e relinca | Acelera ciclos de teste e gravação em bancada de testes. |
| **Acoplamento de Dependências** | Frágil: funções acessam variáveis globais diretamente | Forte encapsulamento: dependências declaradas no `CMakeLists.txt` | Previne poluição de escopo e inclusões circulares de cabeçalho. |
| **Concorrência e Thread Safety** | Risco elevado de conflito de escrita/leitura | Memória protegida por Mutex dedicado em módulo próprio | Elimina corrupção de memória e dados inconsistentes no broker. |
| **Reaproveitamento de Código** | Praticamente nulo sem refatoração | Imediato: a pasta `components/obd2_can` pode ser usada em outro projeto | Viabiliza extensões futuras (ex: telemetria Bluetooth ou 4G LTE). |

---

## 5. Detalhamento dos Módulos Implementados

### 5.1. Módulo `telemetry` (`components/telemetry/`)
* **Papel:** Repositório de dados em tempo real da telemetria veicular.
* **Estrutura:** Mantém uma struct com os PIDs obrigatórios (`rpm`, `temperature`) e opcionais (`speed`), além de marcas temporais e flags de validade.
* **Sincronização:** Todas as escritas (`telemetry_set_*`) e leituras (`telemetry_get_snapshot`) são protegidas por um semáforo de exclusão mútua (`SemaphoreHandle_t s_mutex`).
* **Conformidade de Schema:** O snapshot gerado fornece os dados estruturados de modo compatível com a validação Pydantic do backend (`backend/schemas/telemetry.py`).

### 5.2. Módulo `obd2_can` (`components/obd2_can/`)
* **Papel:** Gestão da camada física e de enlace do barramento automotivo (CAN Bus).
* **Parâmetros de Barramento:** Driver **TWAI** (*Two-Wire Automotive Interface*) configurado nativamente a **500 kbaud** (padrão de fábrica do Volkswagen Polo).
* **Pinagem:** Pinos dedicados ao transceptor SN65HVD230: `TX_PIN = 4`, `RX_PIN = 5`.
* **Tratamento de Interrupção e Anti-Gargalo:**
  * O callback de recepção (`twai_rx_cb`) executa no contexto de interrupção (ISR) de alta prioridade, repassando o frame imediatamente para a fila FreeRTOS `s_rx_queue` sem operações de log ou atraso.
  * O delay bloqueante de 40ms foi substituído por um **FreeRTOS Software Timer** (`can_led_timer`), que desliga o LED de dados de forma 100% assíncrona, eliminando risco de estouro da fila e perda de pacotes CAN.
* **Validação de DLC:** Verificação defensiva de comprimento antes de acessar os bytes de dados (`dlc >= 3` para PIDs gerais, `dlc >= 5` para RPM), prevenindo falhas de segmentação de memória.
* **Consulta Cíclica:** Task `twai_transmit_task` enviando requisições OBD-II padrão (Broadcast `0x7DF`, Modo `0x01`) para RPM (`0x0C`), Velocidade (`0x0D`) e Temperatura do Arrefecimento (`0x05`).

### 5.3. Módulo `wifi_manager` (`components/wifi_manager/`)
* **Papel:** Camada de conectividade de rede local sem fio (Wi-Fi 802.11 b/g/n).
* **Configuração:** Opera estritamente no modo Station (`WIFI_MODE_STA`).
* **Resiliência e Tolerância a Falhas:**
  * Tratamento de eventos `WIFI_EVENT_STA_DISCONNECTED` com lógica de reconexão contínua em caso de perda de sinal ou afastamento do veículo.
  * Sincronização determinística via `EventGroupHandle_t` (`WIFI_CONNECTED_BIT`): o sistema só autoriza o início dos serviços de nuvem após a atribuição efetiva de endereço IP pelo servidor DHCP do roteador/hotspot móvel.

### 5.4. Módulo `mqtt_service` (`components/mqtt_service/`)
* **Papel:** Transporte telemático seguro de dados para a nuvem.
* **Protocolo e Criptografia:** MQTTS sobre TLS v1.2 na porta 8883 direcionado ao broker `test.mosquitto.org`.
* **Autenticação:** O certificado raiz da autoridade certificadora (`mosquitto.org.crt`) foi encapsulado no componente via [ca_cert.h](file:///c:/Users/lucas/Documents/OBDII Scanner/hardware/esp32/components/mqtt_service/include/ca_cert.h) e diretiva `EMBED_TXTFILES`, garantindo validação da cadeia de confiança sem depender de armazenamento em cartão SD ou partição SPIFFS externa.
* **Sinalização Visual no Hardware (Pino D26 / GPIO 26):**
  * O pino **GPIO 26** é inicializado como saída digital em nível baixo.
  * A cada publicação bem-sucedida executada pela task `mqtt_publisher_task`, o pino D26 é levado a nível alto (`1`) e desarmado assincronamente por um temporizador FreeRTOS de **50 ms** (`mqtt_led_timer`).
  * Isso fornece confirmação visual em tempo real durante testes de rodagem no veículo.

### 5.5. Orquestrador `main` (`main/main.c`)
* **Papel:** Coordenação e inicialização do ciclo de vida do sistema.
* **Implementação:** Contém exclusivamente a função `app_main()`, reduzida a 35 linhas de código limpo com macros de checagem de integridade (`ESP_ERROR_CHECK`), garantindo que qualquer falha de alocação de hardware aborte o boot de forma explícita e controlada.

---

## 6. Mapeamento Geral de Pinos de Hardware (Pinout)

| GPIO | Identificação DevKit | Direção | Função no Sistema | Módulo Responsável |
| :---: | :---: | :---: | :--- | :--- |
| **GPIO 4** | D4 | Saída (TX) | Linha de Transmissão CAN para Transceptor SN65HVD230 | `obd2_can` |
| **GPIO 5** | D5 | Entrada (RX) | Linha de Recepção CAN do Transceptor SN65HVD230 | `obd2_can` |
| **GPIO 13** | D13 | Saída Digital | LED Indicador de Sistema Ativo / Alimentação TWAI | `obd2_can` |
| **GPIO 14** | D14 | Saída Digital | LED Indicador de Pacote CAN Recebido da ECU do Veículo | `obd2_can` |
| **GPIO 26** | D26 | Saída Digital | LED Indicador de Pacote Telemático Enviado via MQTT | `mqtt_service` |

---

## 7. Justificativas Acadêmicas e Profissionais para a Banca de TCC

### 7.1. Relevância Acadêmica (Engenharia da Computação)
1. **Atendimento a Critérios de Engenharia:** Transcende o mero funcionamento empírico (*hobbyist approach*) e adota princípios de Engenharia de Sistemas Embarcados com tolerância a falhas, concorrência segura e gestão de memória determinística.
2. **Defesa Teórica Sólida:** Permite ao estudante argumentar perante a banca sobre tópicos essenciais da computação:
   * Sistemas de Tempo Real (RTOS): escalonamento de tarefas, filas inter-threads e timers assíncronos.
   * Redes Industriais/Automotivas: barramento CAN diferencial, arbitragem de barramento e protocolo de aplicação ISO 15765-4.
   * Segurança da Informação: canais seguros TLS aplicados a dispositivos com recursos restritos (IoT Security).

### 7.2. Relevância Profissional e para o Mercado de Trabalho
1. **Padrão da Indústria:** Grandes empresas desenvolvedoras de firmware (indústria automotiva, médica e aeroespacial) exigem arquiteturas modulares orientadas a CMake e aderência a padrões semelhantes ao AUTOSAR e MISRA-C.
2. **Facilidade de Teste e Integração Contínua (CI/CD):** Componentes isolados com interfaces puras permitem o desenvolvimento de testes unitários automatizados (via Unity/CMock) simulando entradas de barramento sem necessidade do veículo físico conectado.

---

## 8. Referências Bibliográficas

1. **BARR, Michael.** *Embedded C Coding Standard.* Germantown: Netrino, 2008.
2. **ESPRESSIF SYSTEMS.** *ESP-IDF Programming Guide: Build System (CMake).* Versão 6.1. Disponível em: <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/build-system.html>. Acesso em: 20 out. 2026.
3. **INTERNATIONAL ORGANIZATION FOR STANDARDIZATION.** *ISO 11898-1: Road vehicles — Controller area network (CAN) — Part 1: Data link layer and physical signalling.* Genebra: ISO, 2015.
4. **INTERNATIONAL ORGANIZATION FOR STANDARDIZATION.** *ISO 15765-4: Road vehicles — Diagnostic communication over Controller Area Network (DoCAN) — Part 4: Requirements for emissions-related systems.* Genebra: ISO, 2021.
5. **ISO/IEC/IEEE.** *ISO/IEC/IEEE 42010: Systems and software engineering — Architecture description.* Piscataway: IEEE, 2011.
6. **MARTIN, Robert C.** *Clean Architecture: A Craftsman's Guide to Software Structure and Design.* Boston: Prentice Hall, 2017.
7. **MISRA.** *MISRA C:2012 — Guidelines for the use of the C language in critical systems.* Nuneaton: HORIBA MIRA Ltd, 2013.
8. **OASIS.** *MQTT Version 3.1.1.* OASIS Standard, 2014. Disponível em: <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html>. Acesso em: 20 out. 2026.
9. **RESCHKE, Julian; FIELDING, Roy.** *RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3.* Internet Engineering Task Force (IETF), 2018.
