"""Apply pending SQL migrations to the Supabase Postgres referenced by DATABASE_URL.

Usage:
    .venv/bin/python migrations/apply.py

Each *.sql file in this directory is executed alphabetically inside a single
transaction. The script is idempotent because every CREATE/ALTER in the
migration uses IF NOT EXISTS / DROP TRIGGER IF EXISTS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set in the environment / .env", file=sys.stderr)
        return 1

    import psycopg  # imported here so the script still helps if psycopg is missing

    migrations_dir = Path(__file__).parent
    sql_files = sorted(p for p in migrations_dir.glob("*.sql"))
    if not sql_files:
        print("No .sql files found in", migrations_dir)
        return 0

    with psycopg.connect(url, autocommit=False) as conn:
        for sql_file in sql_files:
            sql = sql_file.read_text(encoding="utf-8")
            print(f"Applying {sql_file.name} ...")
            with conn.cursor() as cur:
                cur.execute(sql)
        conn.commit()

    print(f"Done. Applied {len(sql_files)} migration file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
