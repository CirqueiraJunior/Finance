# Sprint 07 — Aplicações, Resgates e Saldo Aplicado

## Objetivo

Integrar aplicações e resgates ao fluxo operacional da página Financeiro,
preservando seu armazenamento especializado e suas regras próprias.

## Entregas

- model `InvestmentMovement` e migration `20260824_06`;
- `InvestmentRepository` e `InvestmentService`;
- aplicações e resgates com valores positivos em `Decimal`;
- validação de saldo disponível respeitando a ordem temporal;
- composição de Resultado Operacional, Movimentação de Caixa e Saldo Aplicado;
- tabela única e Novo Lançamento com Receita, Despesa, Aplicação e Resgate;
- integração visual no Financeiro, sem item independente no menu;
- testes de model, repository, service, integração e GUI;
- documentação técnica e funcional.

## Escopo preservado

Não foram implementados rendimentos, juros, rentabilidade, marcação a mercado,
conciliação bancária, múltiplas contas/corretoras complexas, OFX, importação
bancária, BOE detalhado por Entidade, Meta x Realizado, dashboard completo, CSV,
WordPress, autenticação, permissões ou relatórios PDF/Excel.
