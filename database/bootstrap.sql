-- bootstrap.sql: create the application database when absent.
--
-- scripts/initialize_database.py performs the equivalent operation in Python:
-- it checks pg_database and issues CREATE DATABASE with a safely quoted
-- identifier. This file is the canonical SQL reference for manual use:
--
--   psql -d postgres -c "CREATE DATABASE itsm WITH OWNER itsm_owner"
--
-- (run only when the database does not already exist).
CREATE DATABASE itsm WITH OWNER itsm_owner;
