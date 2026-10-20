# Pull Request #03: Fase 1 (Semana 1) — Esteira de Dados e Backend Mock-First

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Backend, Banco de Dados, Frontend e Testes  
**Commit Associado:** [`68ef50ad8c811ad597daab2bf8268babff6eb8f8`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `68ef50a`)  
**Data:** 20 de Setembro de 2026 às 20:16:16 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Este marco representa a entrega dos objetivos da **Semana 1 (Fase 1: Esteira de Dados)** do cronograma do projeto. A estratégia adotada seguiu a metodologia de engenharia de software **Mock-First**: antes de integrar a unidade embarcada ou broker de rede, estabelece-se toda a espinha dorsal de validação de schemas, persistência relacional transacional, APIs de consulta e interface gráfica analítica.

### Objetivos do Marco
1. **Estrutura Modular do Backend:** Inicializar o backend em **FastAPI** particionado em camadas lógicas (rotas, persistência e contratos de dados).
2. **Persistência Transacional (ORM):** Configurar o banco de dados relacional **SQLite** com **SQLAlchemy 2.0**, com controle de sessão e modelo de dados para telemetria veicular.
3. **Contratos e Sanitização de Entrada:** Implementar modelos de validação com **Pydantic v2** para garantir que nenhuma carga malformada ou fora dos limites físicos dos sensores alcance o banco de dados.
4. **Interface Visual (Dashboard):** Criar um painel interativo em **Streamlit** para visualização contínua de métricas em tempo real.
5. **Emulador Veicular (Mock):** Desenvolver um script gerador de telemetria simulada (`scripts/mock_car.py`) que envie dados via requisições HTTP POST para alimentar os primeiros testes funcionais.
6. **Qualidade e Testes:** Estabelecer uma suíte de testes unitários com **pytest**, validando a aceitação e a rejeição sintática de requisições.

```
┌────────────────────────────────────────────────────────────────────────┐
│               FLUXO DA ESTEIRA DE DADOS (SEMANA 1 - HTTP MOCK)         │
└────────────────────────────────────────────────────────────────────────┘

 [ scripts/mock_car.py ] ── Envio de Dados Sintéticos (Requisição HTTP POST)
            │
            ▼
 [ backend/main.py ] ── Endpoint FastAPI: POST /api/v1/telemetry
            │
            ▼
 [ backend/schemas/telemetry.py ] ── Validação Sintática/Semântica (Pydantic v2)
            │
            ▼
 [ backend/database.py ] ── Sessão ACID / Modelo Relacional ORM (SQLAlchemy)
            │
            ▼
 [ vehicle_data.db ] ── Banco de Dados Relacional SQLite
            ▲
            │ Leitura e Ordenação Decrescente: GET /api/v1/telemetry
 [ frontend/app.py ] ── Painel de Controle e Gráficos de Linha (Streamlit)
```

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| `backend/__init__.py` | Criado | +1 / -0 | Converte o diretório em pacote importável Python. |
| [backend/database.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/database.py) | Criado | +34 / -0 | Configuração da engine SQLAlchemy, modelo declarativo `Telemetry` e função geradora `get_db()`. |
| [backend/schemas/telemetry.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/schemas/telemetry.py) | Criado | +21 / -0 | Contratos de validação Pydantic v2: `TelemetryBase`, `TelemetryCreate` e `TelemetryResponse`. |
| [backend/main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/main.py) | Criado | +48 / -0 | Aplicação FastAPI e endpoints `/api/v1/telemetry` (POST para inserção e GET paginado). |
| [frontend/app.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/frontend/app.py) | Criado | +77 / -0 | Painel Streamlit em tempo real renderizando cards de métricas e gráficos temporais de RPM e temperatura. |
| [scripts/mock_car.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/scripts/mock_car.py) | Criado | +33 / -0 | Gerador determinístico de dinâmica veicular despachando telemetria sintetizada via `requests.post`. |
| [backend/tests/test_main.py](file:///c:/Users/lucas/Documents/OBDII%20Scanner/backend/tests/test_main.py) | Criado | +57 / -0 | Suíte de testes com `TestClient` (Starlette/FastAPI) cobrindo rotas HTTP. |
| [requirements.txt](file:///c:/Users/lucas/Documents/OBDII%20Scanner/requirements.txt) | Modificado | +10 / -0 | Fixação de dependências: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `streamlit`, `pandas`, `requests`, `pytest`. |
| [pytest.ini](file:///c:/Users/lucas/Documents/OBDII%20Scanner/pytest.ini) | Criado | +6 / -0 | Parâmetros de execução da suíte de testes automatizados. |
| [README.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/README.md) | Modificado | +153 / -72 | Documentação formal da arquitetura de dados e cronograma em fases do projeto. |

---

## 3. Detalhamento Técnico das Modificações

### 3.1. Modelo Relacional e Persistência (`database.py`)
* **Modelo `Telemetry`:**
  * `id`: Chave primária sequencial inteira indexada.
  * `rpm`: Ponto flutuante não-nulo (rotações por minuto).
  * `temperature`: Ponto flutuante não-nulo (temperatura do arrefecimento em °C).
  * `speed`: Ponto flutuante opcional/anulável (velocidade veicular em km/h).
  * `timestamp`: Carimbo de data/hora em fuso horário UTC (`datetime.now(timezone.utc)`).
* **Gerenciamento de Sessão:** A função `get_db()` opera como um gerador de contexto. A sessão é aberta no início da requisição e, via bloco `finally: db.close()`, o descritor de arquivo é sempre encerrado, prevenindo vazamentos de recursos (*resource leakage*).

### 3.2. Contratos de Dados e Sanitização de Fronteira (`schemas/telemetry.py`)
* O schema `TelemetryCreate` define regras de tipagem estrita para dados de entrada:
  ```python
  class TelemetryCreate(BaseModel):
      rpm: float = Field(..., description="Engine RPM")
      temperature: float = Field(..., description="Engine Coolant Temperature in Celsius")
      speed: Optional[float] = Field(None, description="Vehicle speed in km/h")
  ```
* O schema `TelemetryResponse` adiciona metadados gerados pelo servidor (`id`, `timestamp`) e habilita `from_attributes = True`, permitindo a conversão direta de instâncias ORM para JSON.

### 3.3. Exposição de APIs RESTful (`main.py`)
* Padrão RESTful canônico em inglês, com prefixo versionado `/api/v1/telemetry`.
* O endpoint de leitura implementa paginação com limites superiores (`limit: int = 100`) e ordenação cronológica decrescente (`Telemetry.timestamp.desc()`), assegurando que consultas do painel web recebam prioritariamente as medições mais recentes.

### 3.4. Emulador de Dinâmica Veicular (`mock_car.py`)
* Simulação cíclica de aceleração veicular (RPM variando de 800 a 4500 RPM) e elevação térmica proporcional da água de arrefecimento (70°C a 95°C), enviando requisições com intervalo de 500 ms.

---

## 4. Decisões de Arquitetura e Engenharia de Software

1. **Separação de Preocupações (Separation of Concerns — SoC):**
   A divisão modular em `schemas/`, `database.py` e `main.py` isola regras de validação, motor de banco de dados e roteamento web, facilitando futuras migrações de infraestrutura sem impacto no restante da base.
2. **Princípio da Inversão de Dependência (DIP):**
   O uso de `Depends(get_db)` desacopla as funções de endpoint da instanciação concreta da conexão, permitindo substituir a base de testes por SQLite em memória (`:memory:`) nas baterias do pytest.
3. **Padrão Clean Code & Idioma:**
   Código-fonte (classes, métodos, variáveis) escrito em **Inglês** e documentação/docstrings em **Português**, atendendo ao rigor do meio acadêmico nacional.

---

## 5. Plano de Validação e Testes Automatizados

* **Bateria de Testes (`test_main.py`):**
  * `test_create_telemetry`: Valida a ingestão com sucesso de payload válido, conferindo HTTP 200 e dados persistidos.
  * `test_create_telemetry_invalid`: Injeta carga com tipos inválidos (string no lugar de float). Valida que a FastAPI e o Pydantic interceptam o pacote e retornam HTTP 422 (*Unprocessable Entity*) sem gravar registros no SQLite.
  * `test_read_telemetry`: Valida a leitura da lista histórica com suporte a parâmetros de paginação.
* **Comando de Verificação:**
  ```powershell
  python -m pytest backend/tests/test_main.py
  ```
  *Resultado: 3 testes unitários aprovados.*
