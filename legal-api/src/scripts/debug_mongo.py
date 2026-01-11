import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load .env explicitly
load_dotenv("legal-api/src/.env")

MONGO_URI = os.getenv("MONGO_URI")

async def inspect_mongo():
    if not MONGO_URI:
        print("❌ MONGO_URI not found!")
        return

    print(f"Connecting to MongoDB...")
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        
        # List databases
        dbs = await client.list_database_names()
        print(f"\n📂 Databases found: {dbs}")
        
        target_db = None
        for db_name in dbs:
            if "legal" in db_name or "ghana" in db_name:
                target_db = db_name
                print(f"   -> Potential target DB: {db_name}")
        
        if not target_db:
             # Default to checking 'ghana_legal' or 'legal_expert_db' if present, or just the first non-system one
             target_db = "ghana_legal"

        print(f"\n🔍 Inspecting Database: {target_db}")
        db = client[target_db]
        
        collections = await db.list_collection_names()
        print(f"   📂 Collections: {collections}")
        
        for col_name in collections:
            count = await db[col_name].count_documents({})
            print(f"      - {col_name}: {count} documents")
            
            # Peel into one doc to see structure
            if count > 0:
                doc = await db[col_name].find_one()
                keys = list(doc.keys())
                print(f"        Keys: {keys}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_mongo())
