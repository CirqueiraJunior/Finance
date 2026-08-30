# Manual Técnico — Finance 1.0.0

## Operação multiusuário

O desktop comunica somente com a API FastAPI por HTTPS; a API usa PostgreSQL. Autenticação combina access/refresh token, RBAC é aplicado no servidor, Argon2id protege senhas e AuditLog registra eventos. SMTP e segredos são configurados no ambiente. Use `/health`, Alembic `current/check`, backup e o procedimento de `DEPLOYMENT.md`; SQLite não é a fonte oficial de produção.

## Plataforma e arquitetura

Python 3.13, PySide6, SQLAlchemy 2, Alembic, SQLite em desenvolvimento e
PostgreSQL preparado para produção futura. A arquitetura é
`View -> Controller -> Service -> Repository -> Model`.

`models` define persistência e constraints; `repositories` contém consultas;
`services` valida e coordena transações; `gui/pages` apresenta; `controllers`
liga eventos; `importers` lê fontes externas sem banco; `widgets` centraliza mês,
moeda e decimal.

## Configuração e execução

As variáveis ficam em `.env` conforme `.env.example`. Instale com
`pip install -e ".[dev]"`, aplique `python -m alembic upgrade head` e execute
`python -m app.main`.

## Banco e migrations

O head da 1.0 é `20260828_10`, que adiciona `valor_cancelamento` à Associação
após `20260827_09`. Nunca altere revisões históricas nem faça downgrade no banco
oficial.

## Ranking e Premiação

`RankingService` agrega `TargetEntry` e `AssociationEntry` por trimestre usando
`Decimal`. Classificação exige `>= 100%`; o Score soma Faturamento, Captação e
Cancelamento. A ordenação usa Score decrescente, atingimento decrescente,
Captação decrescente e Cancelamentos crescentes. Empate técnico existe somente
quando os quatro critérios são idênticos e não recebe prêmio automaticamente.
`AwardService` contém os valores oficiais por posição. Nenhum dos serviços cria
`CashflowEntry`.

## Importação e backup

`HistoricalWorkbookImporter` reconhece estruturas oficiais e cria DTOs de
preview. `HistoricalImportService` valida Entidades, catálogo e deduplicação,
aciona `BackupService` e persiste em transação única. BOE reutiliza
`BOEImporter/BOEService`. O backup SQLite usa `sqlite3.Connection.backup`.

Chaves de deduplicação: Fluxo usa período, descrição, categoria, tipo, valor,
BOE e observação; Metas usam Entidade/período/indicador; Associação usa
Entidade/período; Orçamento usa período/tipo/categoria; BOE preserva hash e
período.
Associação persiste Captação, Execução/Total e Cancelamento como conceitos
distintos na mesma chave mensal por Entidade.

## Logs, testes e release

O log rotativo fica em `logs/ja_finance.log` e registra inicialização, erros,
imports, exports e backups sem secrets. Execute `python -m compileall src` e
`python -m pytest -v`. Para release, confirme Alembic, Git limpo após commit
autorizado, aplicação sem warnings e documentação atualizada. A tag não faz
parte desta Sprint.
