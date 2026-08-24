# Orçamento e Orçado x Realizado

## Cadastro

O orçamento é cadastrado por ano, mês, tipo e categoria. A combinação é única e
o valor usa `Decimal`/`Numeric(18, 4)`, podendo ser zero. Categorias e tipos são
os mesmos do Fluxo de Caixa; combinações incompatíveis são bloqueadas no service
e no banco.

Somente valor orçado e observação podem ser editados. Ano, mês, tipo e categoria
permanecem imutáveis. O realizado nunca é digitado ou editado pelo orçamento.

## Realizado

O realizado é agrupado diretamente de `cashflow_entries` por ano, mês, tipo e
categoria. A comparação inclui também categorias realizadas que não possuem
orçamento, com valor orçado zero.

## Desvios

Para receita:

```text
Desvio absoluto = Realizado - Orçado
```

Receita acima do orçamento produz desvio favorável positivo.

Para despesa:

```text
Desvio absoluto = Orçado - Realizado
```

Despesa abaixo do orçamento produz desvio favorável positivo.

Quando o orçamento é maior que zero:

```text
Desvio % = Desvio absoluto / Orçado × 100
```

Quando o orçamento é zero, o percentual é nulo e a GUI apresenta `—`, evitando
divisão por zero. Todos os cálculos usam `Decimal`.

## Resumos

- Receita Orçada e Realizada;
- Despesa Orçada e Realizada;
- Resultado Orçado = Receita Orçada - Despesa Orçada;
- Resultado Realizado = Receita Realizada - Despesa Realizada.

A página suporta visão mensal e anual. Na visão anual os valores mensais são
somados por tipo/categoria. A edição é feita na visão mensal para não haver
ambiguidade entre registros de meses diferentes.

## Fora do escopo

Não há importação automática de orçamento legado, gráficos, exportação,
auditoria avançada, aplicações, resgates ou saldo aplicado.
