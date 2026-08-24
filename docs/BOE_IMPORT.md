# Importação do Faturamento BOE

## Fonte e layout real

A fonte homologada para a Sprint 03 é o arquivo mensal `BOE - 07.26.xlsx`,
recebido do SPC. O fluxo lê exclusivamente a aba `Taxa BOE`; a aba `PRODUTO`
não é aberta nem utilizada.

A planilha usa uma tabela dinâmica na região `E2:G161` quando expandida:

- `E2:G2`: título mesclado `REPASSE BOE - GOIÁS`;
- linha 4: `Row Labels`, `Qtde de Consultas` e `Valor Total`;
- linhas de detalhe: nome da Entidade seguido de seu código na hierarquia;
- linhas finais: consolidados e `Grand Total`;
- podem existir linhas vazias.

Na representação física do `.xlsx`, a tabela dinâmica ocupa `E2:G83`: a linha
4 apresenta `Entidade`, `Qtde de Consultas` e `Valor Total`, e as linhas 5 a 81
contêm 77 nomes com seus totais. Os códigos usados como chave da hierarquia
estão nos metadados da própria tabela dinâmica. O importador associa esses
códigos aos nomes sem consultar a aba `PRODUTO`.

O arquivo de referência não contém período explícito identificável. O período
é obtido pelo fallback controlado do nome `BOE - MM.AA.xlsx`; assim,
`BOE - 07.26.xlsx` corresponde a julho de 2026. Se houver período explícito em
um arquivo futuro, ele tem prioridade.

## Fluxo

```text
Selecionar arquivo -> Validar -> Exibir resultado -> Importar -> Histórico
```

O importador somente abre e interpreta o workbook. Ele produz DTOs em memória e
não conhece SQLAlchemy. O service resolve as Entidades, aplica as regras de
duplicidade e coordena uma única transação de persistência.

## Validações

Erros impedem a importação: arquivo ausente ou diferente de `.xlsx`, workbook
ilegível, aba ou cabeçalhos ausentes, período inválido, código ausente ou
duplicado, valor/quantidade inválido, Entidade desconhecida, hash já importado
ou período já importado.

Avisos não impedem a importação: nome divergente para código conhecido e linha
consolidada `7500` ignorada. O vínculo sempre usa
`entities.codigo_entidade`; o nome e o código originais ficam preservados para
auditoria. Entidades desconhecidas nunca são criadas automaticamente.

## Totais e precisão

Quantidades são inteiras e não negativas. Valores são convertidos para
`Decimal`, com persistência em `Numeric(18, 4)`. O código `7500` não é uma
Entidade: quando presente, serve apenas para conciliar o total calculado das
linhas individuais.

## Duplicidade e rastreabilidade

O arquivo recebe hash SHA-256. Há proteção tanto pelo hash quanto pela combinação
única de ano e mês. A Sprint 03 bloqueia repetição e não implementa
reprocessamento. Cada total guarda o registro de importação, a Entidade vinculada
e o código/nome de origem.

## Resultado do arquivo de referência

A leitura técnica encontrou 77 Entidades, 316.988 consultas e valor total de
`21.967,2684`. Os valores calculados coincidem com o consolidado do arquivo. A
linha consolidada foi ignorada com aviso, conforme a regra do código `7500`.

O parser foi validado sem gravar a planilha oficial no banco. A importação
operacional exige que os 77 códigos já estejam cadastrados na Base Mestra.

## Fora do escopo

Não há análise por produto, comparação de períodos, exportação, dashboard ou
integração com Fluxo de Caixa. A futura integração BOE para Receita Direta
permanece registrada no backlog.
