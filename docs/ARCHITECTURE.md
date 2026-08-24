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

## Fluxo previsto

`View -> Controller -> Service -> Repository -> Model/Database`

Na Sprint 02, `Entity` e `EntityAlias` inauguram o domínio persistente. A regra
do código reservado `7500` permanece no service, enquanto o repository se limita
a consultas e persistência. A GUI continua composta apenas por placeholders.

## Banco de dados

SQLAlchemy 2.x abstrai SQLite em desenvolvimento e PostgreSQL em produção. A URL
vem de `DATABASE_URL`. O Alembic usa o mesmo valor e a metadata de `Base`.
A migration da Sprint 02 contém exclusivamente `entities` e `entity_aliases`.
Os demais módulos funcionais continuam fora do escopo.
