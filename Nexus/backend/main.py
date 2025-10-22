from fastapi import FastAPI, Query
from pydantic import BaseModel
import os, time, json
import psycopg
from psycopg.rows import dict_row

APP_NAME = "GentleΩ Nexus API"
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/metacity")

app = FastAPI(title=APP_NAME)

def get_conn():
    return psycopg.connect(DB_URL, row_factory=dict_row)

@app.get("/health")
def health():
    ok = True
    try:
        with get_conn() as c, c.cursor() as cur:
            cur.execute("select 1")
            _ = cur.fetchone()
    except Exception as e:
        ok = False
    return {
        "status": "ok" if ok else "degraded",
        "ts": int(time.time()),
        "components": {"db": ok}
    }

class AgentCreate(BaseModel):
    name: str
    owner_wallet: str
    meta_uri: str | None = None

@app.post("/api/v1/agents")
def create_agent(a: AgentCreate):
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""INSERT INTO agents(name, owner_wallet, meta_uri)
                       VALUES(%s,%s,%s) RETURNING id""",
                    (a.name, a.owner_wallet, a.meta_uri))
        agent_id = cur.fetchone()["id"]
        c.commit()
        return {"id": agent_id, "status": "created"}

@app.get("/api/v1/ledger")
def ledger(limit: int = Query(20, ge=1, le=200)):
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""SELECT id, poe_hash, tx_hash, block_number, status, updated_at
                       FROM blockchain_ledger ORDER BY id DESC LIMIT %s""", (limit,))
        rows = cur.fetchall()
        return {"items": rows}