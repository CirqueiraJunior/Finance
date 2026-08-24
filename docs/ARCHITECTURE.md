# Arquitetura

O J.A. Finance utiliza arquitetura em camadas e separa apresentação, aplicação,
persistência e infraestrutura.

## Camadas

- `core`: configuração e logging, usados transversalmente.
- `database`: base declarativa, engine e fábrica de sessões.
- `models`: modelos de persistência futuros; vazio nesta sprint.
- `repositories`: fronteira de acesso a dados; sem operações CRUD.
- `services`: casos de uso e regras de aplicação futuras.
- `gui`: janela, páginas e controllers da interface.
- `widgets`: componentes visuais reutilizáveis.
- `resources`: tema e recursos estáticos.
- `reports`: infraestrutura reservada para relatórios.
- `integrations`: infraestrutura reservada para integrações.

## Fluxo previsto

`View -> Controller -> Service -> Repository -> Model/Database`

Na Sprint 01 somente View e Controller de navegação têm comportamento. As demais
camadas são fundações sem regras de negócio.

## Banco de dados

SQLAlchemy 2.x abstrai SQLite em desenvolvimento e PostgreSQL em produção. A URL
vem de `DATABASE_URL`. O Alembic usa o mesmo valor e a metadata de `Base`.
Nenhuma tabela de negócio ou migração inicial foi criada deliberadamente.

