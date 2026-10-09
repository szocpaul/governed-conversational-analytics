#!/usr/bin/env python3
"""T004: Idempotent database initialization.

Applies, in deterministic order:
  1. database/bootstrap.sql equivalent (create application database if absent)
  2. database/schema.sql   (schema, tables, constraints, indexes)
  3. database/roles.sql    (grants/revokes) plus read-only role creation

Safe to run more than once. Requires the PostgreSQL service to be healthy.
"""
import os
import sys
import time

import psycopg
from psycopg import sql

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
GRAPHJIN_DB_USER = os.environ.get("GRAPHJIN_DB_USER", "itsm_readonly")
GRAPHJIN_DB_PASSWORD = os.environ.get("GRAPHJIN_DB_PASSWORD", "change-me-readonly-local-only")

MAINTENANCE_DB = "postgres"


def connect(dbname, autocommit=True):
    return psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=dbname,
        connect_timeout=5, autocommit=autocommit,
    )


def wait_for_server(attempts=30, delay=2.0):
    for i in range(attempts):
        try:
            with connect(MAINTENANCE_DB) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return
        except psycopg.OperationalError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def ensure_database():
    with connect(MAINTENANCE_DB) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DB,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE DATABASE {} WITH OWNER {}").format(
                    sql.Identifier(POSTGRES_DB), sql.Identifier(POSTGRES_USER)))
            print(f"created database {POSTGRES_DB}")
        else:
            print(f"database {POSTGRES_DB} already exists")


def ensure_readonly_role():
    with connect(MAINTENANCE_DB) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (GRAPHJIN_DB_USER,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(GRAPHJIN_DB_USER), sql.Literal(GRAPHJIN_DB_PASSWORD)))
            print(f"created role {GRAPHJIN_DB_USER}")
        else:
            cur.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(GRAPHJIN_DB_USER), sql.Literal(GRAPHJIN_DB_PASSWORD)))
            print(f"role {GRAPHJIN_DB_USER} already exists; password refreshed")


def apply_sql_file(conn, path):
    with open(path, encoding="utf-8") as fh:
        statement = fh.read()
    with conn.cursor() as cur:
        cur.execute(statement)
    print(f"applied {os.path.relpath(path, REPO_ROOT)}")


def main():
    wait_for_server()
    ensure_database()
    ensure_readonly_role()
    with connect(POSTGRES_DB) as conn:
        apply_sql_file(conn, os.path.join(REPO_ROOT, "database", "schema.sql"))
        apply_sql_file(conn, os.path.join(REPO_ROOT, "database", "roles.sql"))
    print("initialization complete")


if __name__ == "__main__":
    sys.exit(main())
