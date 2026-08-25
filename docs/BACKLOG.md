# Backlog

Itens fora do escopo funcional da Sprint 10:

- Criar categorias financeiras parametrizáveis.
- Importar automaticamente o orçamento financeiro legado.
- Calcular Saldo acumulado.
- Permitir migração controlada de saldo aplicado inicial histórico.
- Implementar rendimentos, juros e rentabilidade de aplicações.
- Implementar edição controlada e exclusão lógica.
- Implementar auditoria financeira completa.
- Importar a planilha financeira legada.
- Criar relatórios financeiros.
- Avaliar análise BOE por produto apenas como evolução futura.
- Implementar reprocessamento/cancelamento controlado de BOE.
- Comparar períodos do BOE.
- Criar dashboard BOE.
- Criar relatórios BOE.
- Exportar dados BOE.
- Implementar auditoria completa do BOE.
- Criar notificações do BOE.
- Implementar fechamento mensal.
- Criar cadastro funcional de Entidades na GUI.
- Importar Entidades futuramente a partir das fontes legadas.
- Integrar com CSVs do site em etapa futura.
- Avaliar integração futura com WordPress.
- Importar automaticamente metas e realizados operacionais das fontes legadas.
- Definir autenticação, perfis e permissões.
- Planejar CRUDs de cadastros após validação do domínio.
- Planejar importação e saneamento dos dados legados.
- Planejar exportações e relatórios.
- Definir estratégia de backup, auditoria e recuperação.
- Definir empacotamento e distribuição do aplicativo desktop.
- Planejar release e publicação após homologação das funcionalidades previstas.
- Preparar configuração segura e operação do PostgreSQL em produção.
- Avaliar comparações históricas e detalhamento interativo do Dashboard.

## Sprint 08 — BOE detalhado por Entidade na GUI

Implementado: ao selecionar uma importação BOE, a interface apresenta as
Entidades persistidas com:

- Código;
- Entidade;
- Quantidade de Consultas;
- Valor do Repasse.

Também são apresentados Total de Entidades, Total de Consultas e Valor Total. O
código consolidado `7500` permanece excluído.

## Sprint 09 — Meta x Realizado

Implementado o domínio mensal por Entidade para os indicadores Consultas e
Registros, com cadastro, edição controlada, cálculo de Diferença e Atingimento,
consolidação e página funcional. A importação automática permanece no Backlog.

## Itens preservados após a Sprint 09

- Importação automática de Meta e Realizado;
- Relatórios;
- CSV;
- WordPress;
- Administração;
- Release 1.0.

## Sprint 10 — Dashboard Executivo

Implementado o painel consolidado mensal com indicadores financeiros, BOE,
Orçado x Realizado e Meta x Realizado, além de três gráficos simples. O painel
tolera módulos sem dados e não persiste snapshots ou cálculos próprios.


## Registro de escopo

A Sprint 01 foi homologada em 24/08/2026. A Sprint 02 implementou a Base Mestra
de Entidades. A Sprint 03 implementou a importação resumida mensal do BOE. A
Sprint 04 implementou Receita Direta do BOE e Receita Indireta manual. A Sprint
05 implementou despesas manuais e saldo mensal. A Sprint 06 implementou orçamento
mensal/anual e Orçado x Realizado. A Sprint 07 implementou aplicações, resgates
e saldo aplicado. A Sprint 08 implementou o detalhe BOE por Entidade na GUI. A
Sprint 09 implementou Meta x Realizado operacional. A Sprint 10 implementou o
Dashboard Executivo; os demais itens da lista inicial e da seção preservada
continuam pendentes.
