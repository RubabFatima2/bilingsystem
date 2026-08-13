import os

# Ensure Settings() can build even when the local .env is absent (e.g. CI).
# A well-formed Postgres URL keeps create_engine() happy at import time;
# unit tests never actually connect to this database.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://user:pass@localhost/test",
)
