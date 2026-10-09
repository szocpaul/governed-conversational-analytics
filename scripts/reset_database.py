#!/usr/bin/env python3
"""T006: Clean local reset path.

Drops the application schema (cascade) from the application database.
After reset, run scripts/initialize_database.py then scripts/import_dataset.py
to reproduce the validated dataset from the pinned source revision.

Equivalent Docker Compose reset (destroys all persistent state):
    sudo docker compose down -v
"""
import os
import sys

import psycopg
from psycopg import sql

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
APP_SCHEMA = "itsm"


def main():
    conn = psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
        connect_timeout=5, autocommit=True)
    with conn, conn.cursor() as cur:
        cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
            sql.Identifier(APP_SCHEMA)))
    conn.close()
    print(f"dropped schema {APP_SCHEMA} (cascade) from {POSTGRES_DB}; "
          "run initialize_database.py and import_dataset.py to rebuild")


if __name__ == "__main__":
    sys.exit(main())
