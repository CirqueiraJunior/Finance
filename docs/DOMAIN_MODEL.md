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

## Relacionamento

```text
Entity 1 ───── N EntityAlias
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

- BOE: reconhecerá Entidades pelo código e, quando necessário, por aliases; o
  fluxo principal usará o resumo por Entidade, não a aba `PRODUTO`.
- Fluxo de Caixa: uma importação BOE futura originará Receita Direta automática,
  rastreável e protegida contra duplicidade. Receita Indireta será manual.
- Meta x Realizado: usará a base mestra para associar resultados às Entidades.
- O código `7500` será calculado somente em resultados consolidados futuros.

Essas integrações estão documentadas, mas não foram implementadas na Sprint 02.

