\getenv password MCP_READER_PASSWORD
CREATE EXTENSION IF NOT EXISTS unaccent SCHEMA public;
CREATE ROLE mcp_reader LOGIN PASSWORD :'password' CONNECTION LIMIT 5;
ALTER ROLE mcp_reader SET default_transaction_read_only = on;
ALTER ROLE mcp_reader SET statement_timeout = '3s';
CREATE SCHEMA IF NOT EXISTS marts;
GRANT USAGE ON SCHEMA marts TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO mcp_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO mcp_reader;
GRANT USAGE ON SCHEMA raw TO mcp_reader;
GRANT SELECT (run_date, step, status, finished_at) ON raw.pipeline_runs TO mcp_reader;
