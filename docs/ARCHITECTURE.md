# Arquitetura

O J.A. Finance utiliza arquitetura em camadas e separa apresentação, aplicação,
persistência e infraestrutura.

## Camadas

- `core`: configuração e logging, usados transversalmente.
- `database`: base declarativa, engine e fábrica de sessões.
- `models`: modelos de persistência do domínio.
- `repositories`: fronteira de acesso a dados, sem regras de negócio.
- `services`: casos de uso, validações e coordenação transacional.
- `gui`: janela, páginas e controllers da interface.
- `widgets`: componentes visuais reutilizáveis.
- `resources`: tema e recursos estáticos.
- `reports`: infraestrutura reservada para relatórios.
- `integrations`: infraestrutura reservada para integrações.
- `importers`: leitura de fontes externas e conversão para DTOs, sem acesso ao
  banco de dados.

## Fluxo previsto

`View -> Controller -> Service -> Repository -> Model/Database`

Na Sprint 03, o fluxo BOE segue:

`BoePage -> BOEController -> BOEService -> BOERepository -> SQLAlchemy`

O `BOEImporter` é coordenado pelo service e devolve estruturas temporárias. Ele
não persiste dados. O service valida Base Mestra, duplicidade e transação; o
repository se limita a consultas e persistência. A página BOE é o único módulo
operacional, e as demais páginas permanecem placeholders.

## Banco de dados

SQLAlchemy 2.x abstrai SQLite em desenvolvimento e PostgreSQL em produção. A URL
vem de `DATABASE_URL`. O Alembic usa o mesmo valor e a metadata de `Base`.
A migration da Sprint 02 contém `entities` e `entity_aliases`. A migration da
Sprint 03 adiciona exclusivamente `boe_imports`, `boe_entity_totals` e
`boe_import_issues`. Os demais módulos funcionais continuam fora do escopo.
