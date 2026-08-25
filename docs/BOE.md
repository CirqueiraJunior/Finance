# BOE

## Visão funcional atual

O módulo BOE permite validar e importar o resumo mensal da aba `Taxa BOE` e
consultar importações persistidas. Ao selecionar uma linha do histórico, a mesma
página apresenta o detalhamento por Entidade.

O detalhamento contém:

- Código da Entidade;
- nome oficial da Base Mestra, quando disponível;
- quantidade de Consultas;
- Valor do Repasse com quatro casas decimais;
- totais de Entidades, Consultas e Valor.

O nome encontrado na fonte permanece armazenado em
`boe_entity_totals.nome_entidade_origem`, mesmo quando a interface apresenta o
nome oficial. O vínculo é feito pelo código da Entidade.

## Regra do consolidado

O código `7500` representa linha consolidada da fonte e não uma Entidade. Ele é
ignorado na importação e também filtrado defensivamente na consulta detalhada,
sem afetar quantidade, consultas ou valor total.

## Estados da interface

- sem seleção: `Selecione uma importação para visualizar o detalhamento por Entidade.`;
- importação sem linhas: tabela vazia, totais zerados e mensagem
  `Nenhum detalhamento por Entidade disponível para esta importação.`;
- importação inexistente: aviso neutro, sem falha visual;
- importação válida: tabela ordenada por código e totais derivados do banco.

## Limites desta entrega

A consulta não relê arquivos Excel e não implementa produtos, comparação entre
períodos, dashboard, relatórios, exportação, reprocessamento ou cancelamento.
