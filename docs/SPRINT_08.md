# Sprint 08 — BOE detalhado por Entidade

## Objetivo

Disponibilizar, na página BOE existente, o detalhamento persistido de cada
importação mensal por Entidade, sem reler a planilha de origem.

## Entregas

- seleção de uma importação no histórico BOE;
- tabela com Código, Entidade, Consultas e Valor do Repasse;
- uso preferencial do nome oficial da Base Mestra, preservando internamente o
  nome recebido do arquivo;
- totais calculados sobre as linhas persistidas: Entidades, Consultas e Valor;
- estados neutros para ausência de seleção, importação inexistente e importação
  sem detalhamento;
- proteção defensiva para que o código consolidado `7500` não seja apresentado
  nem contabilizado;
- testes de repository, service e interface.

## Arquitetura e fonte dos dados

O fluxo permanece em camadas:

`BoePage -> BOEController -> BOEService -> BOERepository -> SQLAlchemy`

O repository carrega a importação, totais, Entidades vinculadas e
inconsistências. O service produz um DTO imutável, ordena as Entidades, aplica a
regra do código `7500` e soma consultas e valores com `Decimal`. O controller
reage à seleção do histórico e a View somente apresenta o DTO.

Todos os dados exibidos vêm de `boe_imports`, `boe_entity_totals`, `entities` e
`boe_import_issues`. O arquivo Excel não é reaberto nesta consulta.

## Banco de dados

Nenhuma migration foi necessária. As tabelas criadas na Sprint 03 já armazenam
todo o detalhe exigido nesta Sprint.

## Escopo preservado

Não foram implementados análise BOE por produto, reprocessamento, cancelamento,
comparação entre períodos, dashboard BOE, relatórios, exportação ou auditoria.
Também não foram iniciados Meta x Realizado, Dashboard executivo, Relatórios,
integrações CSV/WordPress, Administração ou Release 1.0.
