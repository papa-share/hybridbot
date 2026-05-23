import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schema.sql"


async def main(url: str) -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("Schema Chainlit initialisé.")


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else ""
    if not db_url:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        import os

        db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise SystemExit("DATABASE_URL manquant.")
    asyncio.run(main(db_url))
