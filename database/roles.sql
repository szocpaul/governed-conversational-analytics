-- roles.sql: owner and read-only roles. Idempotent.
-- The read-only role is the ONLY role granted to the GraphJin runtime.
-- NOTE: the role password is set by scripts/initialize_database.py via a
-- parameterized ALTER ROLE statement; this file contains grants/revokes only.

GRANT CONNECT ON DATABASE itsm TO itsm_readonly;
GRANT USAGE ON SCHEMA itsm TO itsm_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA itsm TO itsm_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE itsm_owner IN SCHEMA itsm
    GRANT SELECT ON TABLES TO itsm_readonly;

-- Defense in depth: explicitly deny writes/DDL for the read-only role.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA itsm FROM itsm_readonly;
