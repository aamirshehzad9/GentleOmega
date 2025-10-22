import sys, os
sys.path.append(os.path.dirname(__file__))

from psycopg_fix import connect_pg
import os
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD", "postgres")

app = FastAPI(title="GentleOmega Test App")

# Test database connection
try:
    pg = connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)
    print(f"✅ Connected to PostgreSQL at {PG_HOST}:{PG_PORT}")
    db_status = "connected"
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    pg = None
    db_status = "disconnected"

@app.get("/health")
def health():
    return {"status": "ok", "database": db_status, "message": "Test app running"}

@app.get("/test")
def test_endpoint():
    return {"message": "Test endpoint working", "database": db_status}

@app.post("/items")
def create_item(content: str, user_id: str):
    try:
        if not pg:
            return {"status": "error", "message": "Database not connected"}
        
        with pg.cursor() as cur:
            cur.execute(
                "INSERT INTO items(content, user_id) VALUES (%s, %s) RETURNING id",
                (content, user_id)
            )
            result = cur.fetchone()
            item_id = result[0] if result else None
        
        return {"status": "success", "id": item_id, "content": content, "user_id": user_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}