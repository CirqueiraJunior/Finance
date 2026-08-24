# Arquitetura

O J.A. Finance utiliza arquitetura em camadas e separa apresentação, aplicação,
persistência e infraestrutura.

## Camadas

- `core`: configuração e logging, usados transversalmente.
- `database`: base declarativa, engine e fábrica de sessões.
- `models`: modelos de persistência do domínio.
- `repositories`: fronteira de acesso a dados, sem regras de negócio.
- `services`: casos de uso, validações e coordenação transacional.
- `gui`: janela, páginas e controllers da interface.
- `widgets`: componentes visuais reutilizáveis.
- `resources`: tema e recursos estáticos.
- `reports`: infraestrutura reservada para relatórios.
- `integrations`: infraestrutura reservada para integrações.
- `importers`: leitura de fontes externas e conversão para DTOs, sem acesso ao
  banco de dados.

## Fluxo previsto

`View -> Controller -> Service -> Repository -> Model/Database`

Na Sprint 03, o fluxo BOE segue:

`BoePage -> BOEController -> BOEService -> BOERepository -> SQLAlchemy`

O `BOEImporter` é coordenado pelo service e devolve estruturas temporárias. Ele
não persiste dados. O service valida Base Mestra, duplicidade e transação; o
repository se limita a consultas e persistência.

Na Sprint 04, `CashflowService` concentra as regras de Receita Direta e Indireta.
O `BOEService` recebe opcionalmente esse service com a mesma sessão e, em novas
importações, prepara o lançamento antes do commit único. Assim, falha no Fluxo
de Caixa também reverte cabeçalho, totais e issues do BOE. A GUI segue
`FinanceiroPage -> CashflowController -> CashflowService -> CashflowRepository`.

Na Sprint 05, o mesmo fluxo atende lançamentos manuais de receita e despesa. O
service valida categorias e calcula o resumo mensal com `Decimal`; a View apenas
apresenta os valores e filtra as opções do diálogo por tipo.

Na Sprint 06, orçamento segue
`OrcamentoPage -> BudgetController -> BudgetService -> BudgetRepository`. O
service também consulta `CashflowRepository` na mesma sessão para calcular o
realizado. Não há dependência do Fluxo de Caixa para o orçamento, nem valor
realizado persistido em `budget_entries`.

## Banco de dados

SQLAlchemy 2.x abstrai SQLite em desenvolvimento e PostgreSQL em produção. A URL
vem de `DATABASE_URL`. O Alembic usa o mesmo valor e a metadata de `Base`.
A migration da Sprint 02 contém `entities` e `entity_aliases`. A migration da
Sprint 03 adiciona exclusivamente `boe_imports`, `boe_entity_totals` e
`boe_import_issues`. Os demais módulos funcionais continuam fora do escopo.
A migration da Sprint 04 adiciona somente `cashflow_entries`, com constraints
de coerência e FK única para `boe_imports`.
A migration da Sprint 05 recria apenas as constraints necessárias para permitir
despesas manuais, sem adicionar tabelas ou colunas.
A migration da Sprint 06 adiciona somente `budget_entries`.
