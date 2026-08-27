# Sprint 11A — Aderência do Fluxo de Caixa às Planilhas Oficiais

## Objetivo

Corrigir o lançamento manual do Fluxo de Caixa para reproduzir a estrutura da
planilha oficial `Controle Financeiro Revisao Ajustado - Macro.xlsm`.

## Fonte oficial

A aba `Lista Suspensa` define as combinações permitidas de:

- Descrição
- Categoria
- Tipo

A aba `Lançamentos` utiliza:

- Ano
- Mês
- Descrição
- Observação
- Categoria
- Tipo
- Valor
- BOE

## Implementação

- catálogo parametrizável em `cashflow_catalog_entries`;
- catálogo inicial semeado pela migration `20260827_09`;
- Descrição selecionável no diálogo Novo Lançamento;
- Ano e Mês selecionáveis, sem exposição do dia;
- Categoria dependente da Descrição;
- Tipo derivado da combinação Descrição + Categoria;
- Tipo apresentado por indicadores de radio button, sem seleção arbitrária;
- BOE Sim/Não persistido em `cashflow_entries`;
- BOE sem valor inicial para Receita/Despesa e validado antes de salvar;
- Valor com entrada brasileira e normalização para `Decimal`;
- Mês apresentado por nome, mantendo o número correspondente internamente;
- digitação monetária automática em centavos, sem uso de `float`;
- coluna BOE exibida no Fluxo de Caixa;
- despesas BOE e não BOE separadas no resumo de domínio;
- Receita Líquida Direta calculável como Receita Direta - Despesas BOE;
- Aplicação e Resgate continuam no mesmo Fluxo de Caixa e não são Receita/Despesa.

## Saldo Aplicado

`Saldo Aplicado` permanece no catálogo de referência, porém não é oferecido como
lançamento manual nesta Sprint. No sistema o saldo aplicado é calculado a partir
de Aplicações e Resgates. A migração de saldos históricos deve ser tratada
separadamente para não criar dupla contagem.

## Compatibilidade

Lançamentos existentes são preservados. A nova coluna `boe` recebe `False`
para registros anteriores. Nenhuma migration anterior foi alterada.
Como `cashflow_entries` ainda possui `data_lancamento`, o primeiro dia do mês
selecionado é gravado internamente. O usuário trabalha apenas com Ano/Mês e a
tabela apresenta o período no formato `MM/AAAA`.

## Fora do escopo

- importação automática da planilha legada;
- migração de saldo inicial;
- edição/exclusão avançada de lançamentos;
- alteração das regras já homologadas do BOE mensal;
- WordPress direto.
