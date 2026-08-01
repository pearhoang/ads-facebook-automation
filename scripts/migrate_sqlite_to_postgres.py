from __future__ import annotations

import argparse

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import Engine

from backend.app import models  # noqa: F401
from backend.app.db import Base


def copy_tables(source: Engine, target: Engine) -> dict[str, int]:
    tables = list(Base.metadata.sorted_tables)
    source_names = set(inspect(source).get_table_names())
    target_names = set(inspect(target).get_table_names())
    missing_source = [table.name for table in tables if table.name not in source_names]
    missing_target = [table.name for table in tables if table.name not in target_names]
    if missing_source or missing_target:
        raise RuntimeError(
            f"Schema mismatch; source missing={missing_source}, target missing={missing_target}"
        )

    counts: dict[str, int] = {}
    with source.connect() as source_connection, target.begin() as target_connection:
        nonempty = {
            table.name: target_connection.scalar(select(func.count()).select_from(table))
            for table in tables
        }
        nonempty = {name: count for name, count in nonempty.items() if count}
        if nonempty:
            raise RuntimeError(f"Target database is not empty: {nonempty}")

        for table in tables:
            rows = [dict(row._mapping) for row in source_connection.execute(select(table))]
            if rows:
                target_connection.execute(table.insert(), rows)
            counts[table.name] = len(rows)

        for table in tables:
            copied = target_connection.scalar(select(func.count()).select_from(table))
            if copied != counts[table.name]:
                raise RuntimeError(
                    f"Row count mismatch for {table.name}: expected={counts[table.name]} actual={copied}"
                )
    return counts


def migrate(source_url: str, target_url: str) -> dict[str, int]:
    source = create_engine(source_url, pool_pre_ping=True)
    target = create_engine(target_url, pool_pre_ping=True)
    try:
        return copy_tables(source, target)
    finally:
        source.dispose()
        target.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy Meta Ads Copilot data between databases")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--target-url", required=True)
    args = parser.parse_args()
    if not args.source_url.startswith("sqlite:///"):
        raise SystemExit("Source URL must be SQLite.")
    if not args.target_url.startswith("postgresql+psycopg://"):
        raise SystemExit("Target URL must use PostgreSQL with psycopg.")
    counts = migrate(args.source_url, args.target_url)
    for table_name, count in counts.items():
        print(f"{table_name}={count}")


if __name__ == "__main__":
    main()
