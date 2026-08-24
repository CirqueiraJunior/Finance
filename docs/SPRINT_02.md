# Sprint 02 — Modelagem do domínio e base mestra de Entidades

## Objetivo

Criar a base mestra de Entidades do J.A. Finance, com modelos persistentes,
aliases, acesso por repository, validações no service e migration inicial do
domínio.

## Escopo

- Modelos `Entity` e `EntityAlias`.
- Relacionamento bidirecional de uma Entidade para muitos aliases.
- Repository específico para consulta e persistência de Entidades.
- Service para criação, consulta, listagem e inclusão de alias.
- Rejeição do código reservado `7500` pelo service.
- Migration apenas das tabelas `entities` e `entity_aliases`.
- Testes automatizados de model, banco, repository e service.

## Fora do escopo

- Importação BOE ou de planilhas.
- Fluxo de Caixa, lançamentos, orçamento ou receitas funcionais.
- Meta x Realizado, ranking ou premiação.
- CSVs, exportações, relatórios, dashboards e gráficos funcionais.
- Autenticação e permissões.
- Integração WordPress.
- CRUD ou tela funcional de Entidades.

As telas existentes permanecem placeholders.

## Decisões de negócio

1. O código `7500` representa o consolidado geral e não uma Entidade real. Seu
   cadastro é rejeitado pelo `EntityService`.
2. O fluxo principal futuro do BOE usará o resumo por Entidade e desconsiderará
   a aba `PRODUTO`.
3. Uma importação BOE futura gerará Receita Direta automática, rastreável e sem
   duplicidade. Receita Indireta será cadastrada manualmente.
4. Nenhuma dessas regras futuras foi implementada nesta Sprint.

## Arquitetura

O fluxo permanece em camadas:

```text
View -> Controller -> Service -> Repository -> Model/Database
```

- Models definem estrutura e integridade relacional.
- Repository encapsula consultas e persistência, sem regra de negócio.
- Service normaliza entradas mínimas, aplica validações e coordena transações.
- GUI não acessa diretamente o domínio nesta Sprint.

## Entidades criadas

### Entity

Tabela `entities`, identificada internamente por `id` e externamente por
`codigo_entidade`, que é obrigatório e único. Contém dados descritivos,
indicador de atividade, observação e timestamps.

### EntityAlias

Tabela `entity_aliases`, vinculada obrigatoriamente a uma Entidade. A combinação
de `entity_id` e `alias` é única, evitando duplicidade óbvia dentro da mesma
Entidade.

## Critérios de aceite

- As duas tabelas são criadas e removidas corretamente pelo Alembic.
- Código de Entidade é único.
- Relacionamento `Entity 1:N EntityAlias` funciona nos dois sentidos.
- Código `7500` é rejeitado exclusivamente no service.
- Repository e service cumprem os contratos definidos.
- Testes antigos e novos passam.
- Aplicação PySide6 continua abrindo sem tela funcional nova.

## Testes

Os testes cobrem persistência, unicidade, relacionamento, consultas do
repository, criação e recuperação via service, código reservado, código
duplicado e aliases.

Resultado da validação técnica em 24/08/2026:

- Python 3.13.15;
- compilação de `src` aprovada;
- `20 passed in 0.31s`;
- migration `20260824_01` validada em upgrade e downgrade;
- `alembic check` sem operações pendentes;
- SQLite contendo somente `entities`, `entity_aliases` e `alembic_version`;
- aplicação PySide6 aberta com sucesso por `python -m app.main`.

Comandos de validação:

```powershell
python -m compileall src
python -m pytest -v
python -m alembic upgrade head
python -m alembic current
```

## Pendências

As integrações e módulos funcionais permanecem no `BACKLOG.md`. Nenhuma etapa
funcional da Sprint seguinte foi antecipada.
