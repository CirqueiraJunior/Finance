# Backlog

- Ajuste visual pequeno: limpar “Selecione uma Entidade.” ao trocar para a aba Catálogo.
- Centralizar backup e importação histórica na API; enquanto isso, essas ações ficam bloqueadas no modo servidor, sem acesso alternativo ao SQLite.

- Validar Sprint 12.A em PostgreSQL isolado na infraestrutura de deploy e homologar envio SMTP real.
- Migrar dados oficiais SQLite → PostgreSQL somente após autorização formal e plano de reversão aprovado.

Itens fora do escopo funcional da Sprint 10:

- Criar categorias financeiras parametrizáveis.
- Importar automaticamente o orçamento financeiro legado.
- Calcular Saldo acumulado.
- Permitir migração controlada de saldo aplicado inicial histórico.
- Implementar rendimentos, juros e rentabilidade de aplicações.
- Implementar edição controlada e exclusão lógica.
- Implementar auditoria financeira completa.
- Importar a planilha financeira legada.
- Evoluir relatórios financeiros com filtros e formatos adicionais.
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
- Evoluir a exportação CSV e avaliar integração direta com o site.
- Avaliar integração futura com WordPress.
- Importar automaticamente metas e realizados operacionais das fontes legadas.
- Definir autenticação, perfis e permissões.
- Planejar CRUDs de cadastros após validação do domínio.
- Planejar importação e saneamento dos dados legados.
- Planejar exportações avançadas e relatórios PDF/Excel.
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
- Relatórios avançados;
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

## Sprint 11 — Relatórios e CSV

Implementados relatório financeiro anual e motor dos cinco CSVs oficiais do site CESPC/GO, com validação de completude e histórico de exportação. Integração direta com WordPress permanece no Backlog.


## Correção concluída — Sprint 11A

- [x] Catálogo Descrição/Categoria/Tipo conforme `Lista Suspensa`
- [x] Categoria dependente da Descrição
- [x] Tipo derivado automaticamente
- [x] Campo BOE Sim/Não nos lançamentos
- [x] Preservação dos lançamentos existentes

## Sprint 12 — Importação histórica controlada

Importação histórica controlada das planilhas oficiais para evitar redigitação
dos meses anteriores.

Contempla Fluxo de Caixa, BOE, Meta x Realizado e os dados necessários
de Associação, com validação antes de gravar, preview, backup, prevenção de
duplicidade, relatório de inconsistências e reconciliação de totais.

### Preservado para evolução posterior após a Release 1.0

- tratamento de saldo inicial/saldo aplicado histórico;
- integração direta com WordPress.

Os itens de importação histórica, Cadastros, Administração e backup foram
concluídos na Sprint 12. Permanecem no backlog os itens futuros já registrados,
como autenticação/permissões, PostgreSQL de produção, auditoria completa,
empacotamento/distribuição e integrações avançadas.

## J.A. Finance 1.1 — Arquitetura Multiusuário

- PostgreSQL central;
- API FastAPI;
- autenticação;
- login;
- cadastro de usuário;
- esqueci minha senha;
- alteração de senha;
- perfis;
- permissões;
- auditoria;
- sessões;
- atualização compartilhada de dados;
- identificação de usuário em lançamentos;
- segurança;
- deploy central.

Proposta inicial de perfis, ainda sujeita à validação: Administrador, Gestor,
Operador Financeiro, Operador BOE e Consulta. Nenhum item desta arquitetura foi
implementado na Release 1.0.
