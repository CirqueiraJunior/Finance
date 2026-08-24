# Sprint 03 — Faturamento BOE

## Objetivo

Implementar a importação do resumo mensal por Entidade da aba `Taxa BOE`, com
validação prévia, vínculo à Base Mestra, persistência transacional, histórico e
uma interface mínima.

## Entregas

- modelos `BOEImport`, `BOEEntityTotal` e `BOEImportIssue`;
- parser isolado em `importers`, DTOs e severidades `ERROR`/`WARNING`;
- identificação do período interno com fallback pelo nome;
- SHA-256 e bloqueio por arquivo ou período duplicado;
- vínculo obrigatório por `Entity.codigo_entidade`;
- repository e service com commit/rollback;
- migration `20260824_02`;
- tela Faturamento BOE com seleção, validação, importação e histórico;
- testes unitários com workbooks controlados;
- documentação do layout real e do fluxo.

## Critérios de segurança

A validação ocorre integralmente antes da persistência. Erros críticos mantêm o
botão Importar desabilitado. O código `7500` é consolidado, Entidades ausentes
não são criadas, e falhas durante a gravação provocam rollback integral.

## Escopo preservado

Não foram implementados Fluxo de Caixa, Receita Direta automática, Receita
Indireta, Metas, CSV, WordPress, produtos BOE, gráficos ou exportações.

## Homologação

A execução técnica deve confirmar `compileall`, toda a suíte `pytest`, ciclo de
upgrade/downgrade da migration, `alembic check`, leitura sem persistência do
arquivo oficial e abertura da aplicação. O resultado efetivo fica registrado no
relatório de execução da Sprint 03.
