# Sprint 04 — Fluxo de Caixa inicial

## Objetivo

Criar a primeira cadeia financeira operacional: uma importação BOE gera uma
Receita Direta rastreável, enquanto Receita Indireta pode ser cadastrada
manualmente.

## Entregas

- `CashflowEntry` e migration `20260824_03`;
- constantes controladas de tipo, origem e categoria;
- `CashflowRepository` e `CashflowService`;
- integração transacional BOE para Receita Direta;
- proteção por service e unicidade de `boe_import_id`;
- Receita Indireta manual com validações;
- página Fluxo de Caixa, resumo, filtro, tabela e diálogo;
- testes de model, repository, service, integração e GUI;
- documentação de domínio e arquitetura.

## Consistência

Uma nova importação BOE e sua Receita Direta compartilham sessão e commit. Uma
falha financeira causa rollback de todos os registros da importação. O BOE já
existente da Sprint 03 é tratado explicitamente durante a homologação, sem
reimportação.

## Fora do escopo

Não foram implementados despesas, orçamento, aplicações, resgates, saldos,
dashboard completo, gráficos, relatórios avançados, Meta x Realizado, CSV,
WordPress, autenticação, permissões ou importação financeira legada.
