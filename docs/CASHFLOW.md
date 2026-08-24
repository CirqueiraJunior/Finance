# Fluxo de Caixa

## Escopo da Sprint 04

O Fluxo de Caixa registra exclusivamente receitas. Receita Direta é criada a
partir de uma importação BOE; Receita Indireta é informada manualmente. Despesas,
saldo, orçamento, aplicações, resgates e contas bancárias não fazem parte desta
Sprint.

## Lançamento financeiro

`CashflowEntry` armazena período, data, descrição, tipo, origem, categoria,
valor `Numeric(18, 4)`, referência opcional ao BOE, observação e timestamps.

Valores controlados:

- tipo: `RECEITA`;
- origem: `BOE` ou `MANUAL`;
- categoria: `RECEITA_DIRETA` ou `RECEITA_INDIRETA`.

O banco impede combinações incoerentes. Origem BOE exige Receita Direta e FK
BOE; origem MANUAL exige Receita Indireta e FK nula. O valor deve ser positivo.

## BOE para Receita Direta

```text
BOEImport imported -> 1 CashflowEntry BOE/RECEITA_DIRETA
```

O valor e o período vêm do consolidado da importação. É criado um único
lançamento, e não um lançamento por Entidade. A descrição usa o período, por
exemplo `Receita Direta BOE 07/2026`.

A FK `boe_import_id` possui índice único. O service também consulta a existência
antes de gravar, oferecendo proteção estrutural e de aplicação.

Novas importações feitas pelo fluxo da aplicação gravam BOE e Receita Direta na
mesma sessão e no mesmo commit. Se a criação financeira falhar, o BOE inteiro é
revertido. Para BOEs existentes antes da Sprint 04, o lançamento é criado uma
única vez pelo caso de uso explícito do `CashflowService`.

## Receita Indireta

O usuário informa ano, mês, data, descrição, valor e observação opcional. O
service fixa tipo `RECEITA`, origem `MANUAL`, categoria `RECEITA_INDIRETA` e
mantém `boe_import_id` nulo. Ano, mês, descrição e valor positivo são validados.

## Interface

A página Fluxo de Caixa oferece filtro por ano/mês, resumo de Receita Direta,
Receita Indireta e Receita Total, tabela somente leitura e diálogo exclusivo
para Nova Receita Indireta. Lançamentos BOE não são editáveis.
