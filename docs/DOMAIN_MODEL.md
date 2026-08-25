# Modelo de domínio

## Entity

`Entity` representa uma Entidade real da base mestra.

| Campo | Tipo | Regra |
| --- | --- | --- |
| `id` | inteiro | Chave primária interna |
| `codigo_entidade` | inteiro | Obrigatório e único; chave de integração |
| `nome` | texto | Obrigatório |
| `nome_oficial` | texto | Opcional |
| `municipio` | texto | Opcional |
| `uf` | texto de 2 caracteres | Opcional, normalizado para maiúsculas no service |
| `sigla` | texto | Opcional |
| `ativa` | booleano | Obrigatório, padrão verdadeiro |
| `observacao` | texto | Opcional |
| `created_at` | data/hora | Obrigatório, preenchido automaticamente |
| `updated_at` | data/hora | Obrigatório, atualizado pelo ORM |

O nome não é usado como chave de integração.

## EntityAlias

`EntityAlias` registra variações de identificação de uma Entidade em fontes
externas ou legadas.

| Campo | Tipo | Regra |
| --- | --- | --- |
| `id` | inteiro | Chave primária |
| `entity_id` | inteiro | FK obrigatória para `entities.id` |
| `alias` | texto | Obrigatório |
| `origem` | texto | Opcional |
| `created_at` | data/hora | Obrigatório, preenchido automaticamente |

A combinação `entity_id + alias` é única. O mesmo texto poderá existir para
Entidades distintas quando fontes externas realmente exigirem isso.

## BOEImport

Representa uma execução mensal do BOE. Ano e mês são únicos em conjunto, e o
hash SHA-256 do arquivo também é único. Guarda nome e caminho de origem, data,
quantidades, valor total `Numeric(18, 4)` e status controlado.

## BOEEntityTotal

Registra o resumo mensal de uma Entidade. Possui FKs obrigatórias para
`BOEImport` e `Entity`, quantidade inteira, valor `Numeric(18, 4)` e cópia do
código e nome de origem para auditoria. Uma Entidade só pode aparecer uma vez em
cada importação.

## BOEImportIssue

Persiste avisos não impeditivos associados à importação, com linha, código,
mensagem e severidade. Erros anteriores à criação do histórico permanecem no
resultado de validação em memória e impedem a transação.

## CashflowEntry

Representa um lançamento de receita no Fluxo de Caixa. Guarda ano, mês, data,
descrição, tipo, origem, categoria, valor `Numeric(18, 4)`, referência opcional
ao BOE, observação e timestamps.

Na Sprint 05, `tipo` aceita `RECEITA` e `DESPESA`. Origem `BOE` exige categoria
`RECEITA_DIRETA` e `boe_import_id`; origem `MANUAL` exige
`RECEITA_INDIRETA` para receita ou uma categoria mínima para despesa, sempre com
FK nula. Constraints reforçam as combinações, período válido e valor positivo.
A unicidade da FK garante no máximo um lançamento por BOE.

## BudgetEntry

Representa o valor orçado de uma categoria em determinado mês. Guarda ano, mês,
tipo, categoria, valor `Numeric(18, 4)`, observação e timestamps. A combinação
ano + mês + tipo + categoria é única. O banco valida período, valor não negativo
e coerência entre tipo e categoria.

`BudgetEntry` não armazena realizado nem possui FK para lançamentos. O realizado
é agregado de `CashflowEntry` no service usando as quatro dimensões comuns.

## InvestmentMovement

Representa uma transferência entre caixa e saldo aplicado. Guarda data do
movimento, ano e mês derivados, tipo `APLICACAO` ou `RESGATE`, descrição, valor
`Numeric(18, 4)` sempre positivo, observação e timestamps. O tipo define o
efeito no saldo; não há persistência com sinal negativo.

Não existe FK para `CashflowEntry`: aplicação não é despesa e resgate não é
receita, embora ambos pertençam ao fluxo operacional do Financeiro. O service
soma aplicações e subtrai resgates até uma data de corte,
impedindo saldo aplicado negativo e o uso de movimentos futuros na validação.

## TargetEntry

Representa uma Meta operacional mensal de uma Entidade para `CONSULTAS` ou
`REGISTROS`. Guarda ano, mês, indicador, Meta, Realizado disponível,
observação e timestamps. Meta e Realizado usam `Numeric(18,4)` e não aceitam
valores negativos.

A combinação Entidade + ano + mês + indicador é única. O Realizado é necessário
porque a fonte oficial está na aba `Faturamento` e ainda não existe em outro
domínio do sistema. Diferença, percentual e consolidados são derivados no
service e não persistidos.

## Relacionamentos

```text
Entity 1 ───── N EntityAlias
Entity 1 ───── N BOEEntityTotal N ───── 1 BOEImport
BOEImport 1 ───── N BOEImportIssue
BOEImport 1 ───── 0..1 CashflowEntry
InvestmentMovement (histórico financeiro independente)
Entity 1 ───── N TargetEntry
```

O relacionamento SQLAlchemy é bidirecional por `Entity.aliases` e
`EntityAlias.entity`. Aliases são dependentes da Entidade e utilizam cascade de
exclusão.

## Código 7500

O código `7500` é reservado ao consolidado geral, correspondente à soma futura
das Entidades. Ele não é armazenado em `entities`.

O `EntityService` rejeita sua criação com `InvalidEntityCodeError` e a mensagem:

```text
O código 7500 representa o consolidado geral e não pode ser cadastrado como Entidade.
```

A regra não reside na GUI nem no repository.

## Integrações futuras

- BOE: reconhece Entidades pelo código; nomes oficiais e aliases servem apenas
  para conferir divergências. O fluxo usa o resumo, nunca a aba `PRODUTO`.
- Fluxo de Caixa: uma importação BOE origina Receita Direta automática,
  rastreável e protegida contra duplicidade. Receita Indireta é manual.
- Meta x Realizado: usa a base mestra para associar Consultas e Registros às
  Entidades pelo código funcional.
- O código `7500` é calculado somente como consolidado e nunca persistido como
  Entidade ou Meta.

Despesas manuais e saldo mensal foram adicionados na Sprint 05, orçamento na
Sprint 06, aplicações/resgates com saldo aplicado na Sprint 07 e Meta x
Realizado na Sprint 09. Rendimentos e demais evoluções continuam futuras.
