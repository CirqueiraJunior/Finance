# Fluxo de Caixa

## Escopo da Sprint 04

O Fluxo de Caixa registra Receita Direta do BOE, Receita Indireta manual e
Despesa manual. O orçamento e as movimentações de investimento pertencem a
módulos próprios e não são categorias do Fluxo de Caixa.

## Lançamento financeiro

`CashflowEntry` armazena período, data, descrição, tipo, origem, categoria,
valor `Numeric(18, 4)`, referência opcional ao BOE, observação e timestamps.

Valores controlados:

- tipo: `RECEITA` ou `DESPESA`;
- origem: `BOE` ou `MANUAL`;
- categorias de receita: `RECEITA_DIRETA` e `RECEITA_INDIRETA`;
- categorias de despesa: `ADMINISTRATIVO`, `DIRETORIA`, `EVENTOS`,
  `OPERACIONAL`, `PESSOAL`, `INVESTIMENTO`, `IMPOSTOS_E_TAXAS`, `SOFTWARE`,
  `VIAGEM` e `OUTROS`.

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

## Despesa manual

Despesa usa tipo `DESPESA`, origem `MANUAL`, uma das categorias mínimas e FK BOE
nula. O valor persistido permanece positivo; o tipo define seu efeito no saldo.
Despesa com BOE ou categoria de receita é bloqueada pelo service e pelo banco.

## Resumo mensal

```text
Receita Total = Receita Direta + Receita Indireta
Resultado Operacional = Receita Total - Despesa Total
Movimentação de Caixa = Receita Total - Despesa Total - Aplicações + Resgates
```

Todos os cálculos usam `Decimal`. Não há saldo acumulado nesta Sprint.

Os lançamentos do Fluxo de Caixa são a fonte exclusiva do realizado na comparação
orçamentária. O módulo de orçamento não altera nem duplica esses valores.

Aplicação e Resgate são movimentações do Fluxo de Caixa, mas não são Receita nem
Despesa. Eles são armazenados em `investment_movements` e apresentados na mesma
tabela do Financeiro. O Saldo Aplicado considera o histórico até o fim do período.

## Interface

A página oferece filtro por ano/mês, sete indicadores, tabela unificada e diálogo
Novo Lançamento com os quatro tipos. Receita permite apenas Receita Indireta;
Receita Direta continua automática via BOE.
