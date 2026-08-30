"""Migração controlada SQLite -> PostgreSQL. Preview é o modo padrão e seguro."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, inspect, select


@dataclass(frozen=True, slots=True)
class TableCount:
    table: str
    source: int
    target: int


def analyze(source_url: str, target_url: str) -> list[TableCount]:
    source = create_engine(source_url)
    target = create_engine(target_url)
    if source.dialect.name != "sqlite" or target.dialect.name != "postgresql":
        raise ValueError("Origem deve ser SQLite e destino deve ser PostgreSQL.")
    metadata = MetaData()
    metadata.reflect(source)
    target_tables = set(inspect(target).get_table_names())
    result = []
    with source.connect() as src, target.connect() as dst:
        for table in metadata.sorted_tables:
            if table.name == "alembic_version" or table.name not in target_tables:
                continue
            destination = MetaData().tables.get(table.name)
            target_metadata = MetaData()
            target_metadata.reflect(target, only=[table.name])
            destination = target_metadata.tables[table.name]
            result.append(TableCount(table.name, src.scalar(select(func.count()).select_from(table)) or 0,
                                     dst.scalar(select(func.count()).select_from(destination)) or 0))
    return result


def migrate(source_url: str, target_url: str) -> list[TableCount]:
    source = create_engine(source_url)
    target = create_engine(target_url)
    source_meta, target_meta = MetaData(), MetaData()
    source_meta.reflect(source)
    target_meta.reflect(target)
    with source.connect() as src, target.begin() as dst:
        for table in source_meta.sorted_tables:
            if table.name == "alembic_version" or table.name not in target_meta.tables:
                continue
            destination = target_meta.tables[table.name]
            if (dst.scalar(select(func.count()).select_from(destination)) or 0) != 0:
                raise RuntimeError(f"Destino não vazio: {table.name}. Migração cancelada.")
            rows = [dict(row) for row in src.execute(select(table)).mappings()]
            if rows:
                dst.execute(destination.insert(), rows)
    return analyze(source_url, target_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview e migração controlada SQLite -> PostgreSQL")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    counts = analyze(args.source, args.target)
    for item in counts:
        print(f"{item.table}: origem={item.source} destino={item.target}")
    if not args.execute:
        print("PREVIEW concluído; nenhum dado foi alterado.")
        return 0
    if args.confirm != "MIGRAR PARA POSTGRESQL":
        raise SystemExit("Execução recusada: confirmação explícita ausente.")
    reconciled = migrate(args.source, args.target)
    if any(item.source != item.target for item in reconciled):
        raise SystemExit("Reconciliação falhou; transação deve ser investigada.")
    print("Migração e reconciliação concluídas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
