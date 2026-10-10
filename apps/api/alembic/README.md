# Alembic migrations

Use the repository-level `alembic.ini` to run migrations:

```bash
export ROAD_RISK_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/road_risk"
alembic -c alembic.ini upgrade head
```

Reset a local development database and replay the full migration chain:

```bash
dropdb --if-exists road_risk
createdb road_risk
alembic -c alembic.ini upgrade head
```
