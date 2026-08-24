# Sprint 05 — Despesas e saldo mensal

## Objetivo

Evoluir o Fluxo de Caixa para aceitar despesas manuais classificadas em
categorias mínimas e calcular o saldo do mês, preservando as Receitas Direta do
BOE e Indireta manual.

## Entregas

- tipo `DESPESA` em `CashflowEntry`;
- dez categorias simples de despesa;
- constraints de coerência atualizadas;
- `CashflowService.create_expense`;
- resumo mensal com receitas, despesas e saldo;
- migration `20260824_04`;
- diálogo unificado Novo Lançamento;
- cinco cards e tabela com tipo;
- testes de model, service, resumo e GUI.

## Regras

Receita BOE permanece automática e vinculada. Receita Indireta permanece
manual. Despesa é sempre manual, possui categoria de despesa, valor positivo e
nenhuma referência BOE. O tipo determina se o valor compõe entrada ou saída.

## Fora do escopo

Não foram implementados orçamento, Orçado x Realizado, aplicações, resgates,
saldo aplicado, saldo acumulado, dashboard, gráficos, Meta x Realizado,
integrações CSV/WordPress, autenticação, permissões ou importação legada.
