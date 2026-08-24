# Aplicações, Resgates e Saldo Aplicado

## Conceito financeiro

Aplicação transfere recurso do caixa para o saldo aplicado. Resgate transfere
recurso do saldo aplicado para o caixa. Aplicação não é despesa e resgate não é
receita. Ainda assim, ambas pertencem operacionalmente ao Fluxo de Caixa.

## Movimentos

`InvestmentMovement` registra data, período derivado da data, tipo, descrição,
valor `Numeric(18, 4)`, observação e timestamps. Os tipos são `APLICACAO` e
`RESGATE`. O valor é sempre positivo e todos os cálculos usam `Decimal`.

## Saldo e validação temporal

```text
Saldo Aplicado = Total de Aplicações - Total de Resgates
Movimentação de Caixa = Receitas - Despesas - Aplicações + Resgates
```

O saldo inicial da Sprint 07 é zero. Um resgate só é aceito quando seu valor é
menor ou igual ao saldo disponível naquela data. Movimentos futuros não são
usados para autorizar um resgate anterior. O saldo ao fim do mês considera todo
o histórico até o último dia do período.

## Interface

A página Financeiro reúne Receita, Despesa, Aplicação e Resgate na mesma tabela.
O botão Novo Lançamento oferece os quatro tipos. Os cards distinguem Resultado
Operacional, Movimentação de Caixa e Saldo Aplicado. O diálogo informa o saldo
disponível ao selecionar Resgate e bloqueia valor superior.

## Limites da Sprint 07

Não há rendimento automático, juros, rentabilidade, marcação a mercado, saldo
inicial histórico, conciliação bancária, contas/corretoras complexas, OFX ou
importação bancária.
