import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine

async def test_sqlalchemy():
    from ghana_legal.config import settings
    # Override settings to use our string
    settings.DATABASE_URL = "postgresql+asyncpg://postgres.lpbngcxespbxlhcvaurf:NXXnOtv46N9EodUX@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"

    print(f"Testing engine: {settings.DATABASE_URL.replace('NXXnOtv46N9EodUX', '***')}")
    try:
        from ghana_legal.infrastructure.database import get_engine, init_db
        print("Running init_db()...")
        await init_db()
        print("TABLES INITIALIZED SUCCESSFULLY")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_sqlalchemy())
