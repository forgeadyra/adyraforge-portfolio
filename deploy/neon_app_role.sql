-- Least-privilege runtime role for the Django app (see DEPLOY.md §1).
--
-- Run ONCE in the Neon SQL editor, connected as the database owner: the role whose
-- URL becomes MIGRATION_DATABASE_URL, which the release command uses for `migrate`.
-- Create the role here with SQL, not in the Neon console: console-created roles join
-- neon_superuser. Replace the password placeholder in the editor only. Never save it
-- to this file or commit it.
--
-- The app role can read and write rows. It cannot create, alter or drop tables,
-- so a SQL-injection or RCE in the app cannot change the schema or drop data wholesale.

CREATE ROLE adyraforge_app WITH LOGIN PASSWORD 'REPLACE-IN-EDITOR-ONLY'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
  CONNECTION LIMIT 20;

-- Nobody but the owner creates objects in public.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO adyraforge_app;
GRANT CONNECT ON DATABASE neondb TO adyraforge_app;  -- your database name

-- Existing tables and sequences (if migrations already ran) ...
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO adyraforge_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO adyraforge_app;

-- ... and everything future migrations create (run as the owner, so these apply).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO adyraforge_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO adyraforge_app;

-- Verify: every boolean must be false.
SELECT a.rolname, a.rolsuper, a.rolcreatedb, a.rolcreaterole, a.rolbypassrls,
       EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = a.oid) AS member_of_any_role
FROM pg_roles a WHERE a.rolname = 'adyraforge_app';
