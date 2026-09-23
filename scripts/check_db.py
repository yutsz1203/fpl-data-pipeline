"""Check that Python can connect to the warehouse and that the raw schema exists."""

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

conninfo = (
    f"host={os.environ['POSTGRES_HOST']} port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

with psycopg.connect(conninfo) as conn:
    version = conn.execute("select version()").fetchone()[0]
    schemas = [
        row[0]
        for row in conn.execute(
            "select schema_name from information_schema.schemata order by 1"
        )
    ]

print(version)
print("schemas:", schemas)
assert "raw" in schemas, "raw schema is missing"
print("OK")
