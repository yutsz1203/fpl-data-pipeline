"""Check that Python can connect to the warehouse and that the raw schema exists."""

from db import connect

with connect() as conn:
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
