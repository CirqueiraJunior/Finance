# Arquitetura

No modo servidor (`FINANCE_API_URL` configurada), o `MainWindow` seleciona exclusivamente adapters HTTP antes de criar qualquer sessão. Repositories SQLAlchemy do desktop são instanciados apenas no modo local. Financeiro, BOE, Orçamento, Metas, Ranking, Dashboard, Relatórios, Entidades e Catálogo usam rotas explícitas `/api/v1`; não existe fallback silencioso para SQLite.

> Produção na pré-release 1.0.0: Desktop PySide6 → HTTPS → FastAPI → PostgreSQL. O acesso direto do desktop ao PostgreSQL é proibido. Veja `MULTIUSER_ARCHITECTURE.md`.

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

Na Sprint 07, a operação segue pela página única Financeiro:
`FinanceiroPage -> CashflowController -> FinancialFlowService`. O serviço de
composição consulta `CashflowService` e `InvestmentService` com a mesma sessão.
Internamente, `InvestmentMovement` e `InvestmentRepository` permanecem
especializados para preservar baixo acoplamento e a validação temporal do saldo.

Na Sprint 08, a seleção do histórico BOE usa o mesmo fluxo em camadas da
importação. `BOERepository` carrega importação, totais, Entidades e issues;
`BOEService` converte esse agregado em um DTO imutável, aplica a exclusão
defensiva do código consolidado `7500` e calcula os totais com `Decimal`;
`BOEController` coordena a seleção; e `BoePage` somente apresenta os dados. A
consulta usa exclusivamente o banco e não reabre a planilha Excel.

Na Sprint 09, Meta x Realizado segue
`MetasPage -> TargetController -> TargetService -> TargetRepository -> SQLAlchemy`.
`TargetEntry` é um domínio próprio e não reutiliza `BudgetEntry`. O service
valida a Base Mestra, protege o código `7500`, calcula diferença e atingimento
com `Decimal` e consolida somente Entidades reais. O Realizado operacional vem
conceitualmente da aba `Faturamento` da planilha oficial e, por ainda não existir
em outro módulo, é persistido no próprio registro sem importação automática.

Na Sprint 10, o Dashboard Executivo segue
`DashboardPage -> DashboardController -> DashboardService`. O service é uma
camada de composição somente leitura: reutiliza `FinancialFlowService`,
`BOEService`, `BudgetService` e `TargetService`, todos na mesma sessão, e devolve
DTOs imutáveis. A View apenas formata os indicadores e constrói no máximo três
gráficos simples. Ausência de dados em um módulo não impede a apresentação dos
demais.

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
A migration da Sprint 07 adiciona somente `investment_movements`.
A Sprint 08 não exige migration: utiliza as tabelas BOE já existentes desde a
Sprint 03.
A migration da Sprint 09 adiciona somente `target_entries`.
A Sprint 10 não exige migration nem novos modelos: o Dashboard consulta
exclusivamente os domínios já persistidos.


Na Sprint 11, `RelatoriosPage -> ReportController -> ReportService/SiteCSVService`. O relatório anual apenas compõe serviços existentes. `SiteCSVService` lê Base Mestra, Meta x Realizado e Associação persistida, valida os 12 meses e grava histórico em `csv_exports`; os arquivos usam os contratos oficiais e não dependem de Excel ou WordPress.


## Catálogo de Fluxo de Caixa — Sprint 11A

`cashflow_catalog_entries` é a fonte parametrizável para as combinações
Descrição/Categoria/Tipo do lançamento manual. A GUI consulta o catálogo por
`CashflowCatalogService`; regras não ficam hardcoded no Controller.

A coluna `cashflow_entries.boe` preserva o marcador Sim/Não da planilha
financeira oficial. O catálogo inclui `SALDO`, porém o saldo aplicado continua
derivado de `investment_movements`.

## Release 1.0 — Sprint 12

Cadastros segue `CadastrosPage -> RegistrationController ->
EntityService/CashflowCatalogService -> repositories`. Alterar o catálogo não
reescreve lançamentos históricos.

Administração segue `AdministracaoPage -> AdministrationController ->
AdministrationService/BackupService`. O backup SQLite usa a API nativa de
backup, nome único e validação do arquivo resultante.

A importação histórica segue `HistoricalImportDialog ->
HistoricalImportController -> HistoricalImportService ->
HistoricalWorkbookImporter`. O importer é somente leitura; o service valida a
Base Mestra e o catálogo, detecta duplicidades, cria backup antes da persistência
e executa commit único ou rollback integral. O BOE reutiliza exclusivamente o
`BOEImporter` homologado. Nenhum novo modelo ou migration foi necessário.
