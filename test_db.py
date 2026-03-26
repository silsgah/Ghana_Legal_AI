import asyncio
import asyncpg
import sys

async def test_conn():
    url = "postgresql://postgres.lpbngcxespbxlhcvaurf:NXXnOtv46N9EodUX@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"
    print(f"Connecting to: {url.replace('NXXnOtv46N9EodUX', '***')}")
    try:
        conn = await asyncpg.connect(url)
        print("CONNECTION SUCCESSFUL!")
        await conn.close()
    except Exception as e:
        print(f"CONNECTION FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
