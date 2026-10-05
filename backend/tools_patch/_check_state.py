import os, psycopg
from sqlalchemy import create_engine, text
TEST = "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios_test"
for label, url in (("prod", os.getenv("DATABASE_URL") or "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/furui_aios"), ("test", TEST)):
    e = create_engine(url)
    with e.connect() as c:
        v = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        n = c.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
        rls = c.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND rowsecurity")).scalar()
        es = c.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='edge_sites'")).scalar()
        print(f"{label}: ver={v} tables={n} rls_tables={rls} edge_sites(rowsecurity,force)={es}")
    e.dispose()
