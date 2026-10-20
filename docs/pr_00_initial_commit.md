# Pull Request #00: Configuração Inicial do Repositório e Licenciamento Aberto

**Projeto:** Central de Análise Veicular Preditiva (IoT)  
**Curso:** Engenharia da Computação — Trabalho de Conclusão de Curso (TCC)  
**Módulo:** Governança e Controle de Versão  
**Commit Associado:** [`6b5083df8525190a5981708ec6e67495fce34507`](file:///c:/Users/lucas/Documents/OBDII%20Scanner) (Abrev: `6b5083d`)  
**Data:** 20 de Maio de 2026 às 09:55:36 -0300  
**Autor:** Lucas Praxedes `<praxedes158@gmail.com>`  

---

## 1. Resumo Executivo e Objetivos

Este marco inicial estabeleceu a fundação de controle de versão distribuído do projeto com **Git**, definindo a política de licenciamento de software aberto e instituindo regras sólidas de descarte de artefatos compilados, arquivos efêmeros e caches de ambiente de desenvolvimento.

### Objetivos do Marco
* Criar a estrutura inicial de versionamento no GitHub.
* Adotar formalmente a licença de software livre **GNU General Public License v3.0 (GPL-3.0)**, garantindo a proteção dos direitos intelectuais e assegurando que trabalhos derivados permaneçam de código aberto.
* Configurar o arquivo `.gitignore` com filtros abrangentes para projetos heterogêneos (C/C++ embarcado com CMake/ESP-IDF e Python com ambientes virtuais).
* Padronizar o tratamento de quebras de linha entre sistemas operacionais (Windows e Linux).

---

## 2. Arquivos Modificados e Criados

| Arquivo | Status | Linhas (+/-) | Descrição Técnica |
| :--- | :---: | :---: | :--- |
| [LICENSE](file:///c:/Users/lucas/Documents/OBDII%20Scanner/LICENSE) | Criado | +674 / -0 | Texto integral dos termos da licença pública **GNU GPL v3.0**. |
| [.gitignore](file:///c:/Users/lucas/Documents/OBDII%20Scanner/.gitignore) | Criado | +52 / -0 | Diretivas de exclusão para arquivos compilados, temporários e caches. |
| [.gitattributes](file:///c:/Users/lucas/Documents/OBDII%20Scanner/.gitattributes) | Criado | +2 / -0 | Normalização de caracteres de fim de linha (`text=auto`). |
| [README.md](file:///c:/Users/lucas/Documents/OBDII%20Scanner/README.md) | Criado | +2 / -0 | Título e identificação inicial do projeto. |

---

## 3. Detalhamento Técnico das Modificações

### 3.1. Regras de Exclusão de Artefatos (`.gitignore`)
Por se tratar de um projeto que envolve programação de microcontroladores (firmware) e desenvolvimento de aplicações web/dados (Python), o arquivo `.gitignore` foi configurado para mitigar a poluição do repositório por binários e dependências locais:
* **Ambiente Python:** Exclusão de diretórios de bytecodes (`__pycache__/`, `*.pyc`), ambientes virtuais (`venv/`, `env/`) e artefatos de empacotamento (`*.egg-info/`, `dist/`).
* **Ambiente C/CMake/ESP-IDF:** Descarte de diretórios de compilação gerados pelo CMake e Ninja (`build/`, `*.bin`, `*.elf`, `*.map`, `*.o`, `*.a`).
* **IDEs e Sistemas Operacionais:** Supressão de metadados locais de editores (`.vscode/`, `.idea/`) e arquivos de sistema (`Thumbs.db`, `.DS_Store`).

### 3.2. Normalização de Quebras de Linha (`.gitattributes`)
A definição `* text=auto` instrui o Git a gerenciar automaticamente as conversões de quebra de linha CRLF (Windows) e LF (Linux/POSIX), evitando commits espúrios decorrentes de desenvolvedores operando em diferentes plataformas.

---

## 4. Avaliação de Engenharia e Critérios de Aceitação

* **Rastreabilidade Limpa:** Repositório inicializado sem a inclusão acidental de artefatos compilados ou segredos de ambiente.
* **Conformidade Legal:** Todos os requisitos para projetos de código aberto atendidos via GNU GPL-3.0.
