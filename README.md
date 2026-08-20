# eipc-fw

Monorepo de firmware industrial EIPC (Instituto Curvelo / Bralyx).

| Pasta        | Conteúdo                                                          |
|--------------|--------------------------------------------------------------------|
| `eipc-mb`    | Firmware da Main Board — STM32, CMake nativo, FreeRTOS, QP/C       |
| `eipc-iot`   | Firmware do Gateway IoT — ESP32, ESP-IDF                          |
| `eipc-front` | Interface web de configuração — SvelteKit                        |
| `docs`       | Documentação e manuais compartilhados (Typst/Marp)                |

## Como contribuir

Usamos **GitHub Flow**:

- `main` é a branch de desenvolvimento, sempre a mais atualizada.
- Toda mudança nasce em uma branch derivada de `main` e volta via Pull Request.
- Para lançar uma versão, deriva-se uma branch de release (`v0`, `v1`, ...) a partir de `main`. Fixes e features daquela versão acontecem nela, sem travar a evolução de `main`.
- Gerenciamos o trabalho com GitHub Issues. PRs são sempre via **squash merge**.

```mermaid
gitGraph
    commit id: "chore: setup inicial"
    commit id: "feat: bootstrap bsp"
    branch feat/modbus-driver
    checkout feat/modbus-driver
    commit id: "feat: driver modbus rtu"
    checkout main
    merge feat/modbus-driver
    branch v0
    checkout v0
    commit id: "v0.1.0" tag: "v0.1.0"
    checkout main
    commit id: "feat: telemetry mqtt"
    checkout v0
    branch fix/v0-heap-leak
    checkout fix/v0-heap-leak
    commit id: "fix: vazamento de heap"
    checkout v0
    merge fix/v0-heap-leak
    commit id: "v0.1.1" tag: "v0.1.1"
    branch fe/update fonts
    checkout fe/update fonts
    commit id: "fe: update fonts"
    checkout main
    merge fe/update fonts
    commit id: "fe: update fonts"
```

## Convenções

### Branches

`<tipo>/<escopo-curto>` quando não há issue, `<tipo>/#<número>` quando há.

- `feat/` — nova funcionalidade
- `fix/` — correção de bug
- `refactor/` — refatoração sem mudança de comportamento
- `docs/` — documentação
- `chore/` — manutenção, deps, configs
- `test/` — testes

Ex.: `feat/modbus-crc` (sem issue), `fix/42` (issue #42)

### Commits

[Conventional Commits](https://www.conventionalcommits.org/): `tipo(escopo): descrição`

```
feat(mb/core): adiciona fsm de boot
fix(iot/mqtt): corrige reconexão apos timeout
```
