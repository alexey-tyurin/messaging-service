
import asyncio
import os
import sys
from sqlalchemy import text
from app.db.session import db_manager

# Add path
sys.path.append(os.getcwd())

async def check_schema():
    db_manager.init_db()
    async with db_manager.session_context() as session:
        print("\n--- Conversations Attributes ---")
        # Query information_schema to get column names
        result = await session.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'conversations'"
        ))
        rows = result.fetchall()
        for row in rows:
            print(f"Column: {row.column_name}, Type: {row.data_type}")

if __name__ == "__main__":
    asyncio.run(check_schema())
