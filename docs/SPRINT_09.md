# Sprint 09 — Meta x Realizado

## Objetivo

Implementar o domínio operacional de Meta x Realizado com base na planilha
oficial, sem reutilizar o orçamento financeiro.

## Entregas

- análise documentada das sete abas da fonte oficial;
- model `TargetEntry` e migration `20260825_07`;
- indicadores `CONSULTAS` e `REGISTROS`;
- repository com consultas por ID, período, Entidade e ano;
- service com cadastro, edição controlada, consolidação e cálculos;
- página Metas funcional com filtros, cards, tabela, Nova Meta e edição;
- proteção do código consolidado `7500`;
- testes de model, repository, service, integração e GUI.

## Decisão sobre o Realizado

O Realizado operacional vem da aba `Faturamento`. Não é o valor ou a quantidade
do BOE e não deriva do Fluxo de Caixa. Como essa fonte ainda não possui domínio
persistido no sistema e a importação automática está fora do escopo, o valor
disponível é registrado no `TargetEntry`. Ele não pode ser alterado pelo diálogo
de edição de Meta.

## Escopo preservado

Não foram iniciados Dashboard executivo, Relatórios, integrações CSV/WordPress,
Administração, Release 1.0, ranking, gráficos ou importação automática.
