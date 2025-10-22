import sys, os
sys.path.append(os.path.dirname(__file__))  # adds D:\GentleOmega\app to import path

from psycopg_fix import connect_pg
import os, time, uuid
from typing import List, Dict, Any
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import numpy as np

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB   = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD", "postgres")

app = FastAPI(title="GentleOmega Orchestrator")

# --- PostgreSQL connection ---
try:
    pg = connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)
    print(f"✅ Connected to PostgreSQL at {PG_HOST}:{PG_PORT}")
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")
    pg = None

DIM = 384

@app.get("/health")
def health():
    db_status = "connected" if pg else "disconnected"
    return {"status": "ok", "dim": DIM, "database": db_status}

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

@app.get("/items/count")  
def get_items_count():
    try:
        if not pg:
            return {"status": "error", "message": "Database not connected"}
        
        with pg.cursor() as cur:
            cur.execute("SELECT count(*) FROM items")
            count = cur.fetchone()[0]
        
        return {"status": "ok", "count": count}
    except Exception as e:
        return {"status": "error", "error": str(e)}