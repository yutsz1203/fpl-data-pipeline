\getenv password METABASE_READER_PASSWORD
CREATE ROLE metabase_reader LOGIN PASSWORD :'password';
CREATE SCHEMA IF NOT EXISTS marts;
GRANT USAGE ON SCHEMA raw, marts TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, marts TO metabase_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw, marts GRANT SELECT ON TABLES TO metabase_reader;
