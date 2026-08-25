# Dashboard Executivo

O Dashboard Executivo consolida, por ano e mês, informações já calculadas pelos
serviços dos módulos existentes. Ele não possui regras de negócio próprias, não
persiste snapshots e não altera dados.

## Fontes

- Financeiro: `FinancialFlowService`, com receitas, despesas, resultado
  operacional, movimentação de caixa, aplicações, resgates e saldo aplicado.
- BOE: `BOEService`, com total de Entidades, Consultas e valor de repasse.
- Orçamento: `BudgetService`, com Orçado x Realizado de Receitas, Despesas e
  Resultado.
- Meta x Realizado: `TargetService`, mantendo Consultas e Registros separados.

Todos os valores monetários e percentuais são calculados com `Decimal` nos
serviços de origem. A conversão para ponto flutuante ocorre somente na montagem
visual dos gráficos do Qt.

## Interface

O usuário seleciona ano e mês e aciona **Atualizar**. O painel apresenta cartões
de resumo, uma tabela Orçado x Realizado e três gráficos simples: Financeiro,
Orçamento e Meta x Realizado.

Se BOE, Orçamento ou Meta x Realizado não tiverem dados no período, o módulo
exibe estado vazio e valores neutros sem impedir que os demais módulos sejam
carregados. Um período inteiramente vazio também é suportado.

## Limites da Sprint 10

Não foram adicionados modelos, tabelas, migrations, importações, exportações,
relatórios, autenticação, permissões ou regras de fechamento. Comparações
históricas, detalhamento interativo e demais evoluções permanecem para sprints
futuras, conforme priorização do Backlog.
