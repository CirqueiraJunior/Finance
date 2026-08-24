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

Na Sprint 04, `tipo` aceita somente `RECEITA`. Origem `BOE` exige categoria
`RECEITA_DIRETA` e `boe_import_id`; origem `MANUAL` exige
`RECEITA_INDIRETA` e FK nula. Constraints no banco reforçam essas combinações,
período válido e valor maior que zero. A unicidade da FK garante no máximo um
lançamento por BOE.

## Relacionamentos

```text
Entity 1 ───── N EntityAlias
Entity 1 ───── N BOEEntityTotal N ───── 1 BOEImport
BOEImport 1 ───── N BOEImportIssue
BOEImport 1 ───── 0..1 CashflowEntry
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
- Meta x Realizado: usará a base mestra para associar resultados às Entidades.
- O código `7500` será calculado somente em resultados consolidados futuros.

O Fluxo de Caixa inicial foi implementado na Sprint 04. Despesas e demais
evoluções financeiras continuam futuras.
