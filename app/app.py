import sys, os
sys.path.append(os.path.dirname(__file__))  # adds D:\GentleOmega\app to import path

from psycopg_fix import connect_pg  # sets pure-python mode and helper
import os, time, uuid, asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
import numpy as np
from openai import OpenAI

# Import blockchain integration
from blockchain_client import record_pod, record_poe, cleanup_blockchain_client

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

HF_TOKEN        = os.getenv("HF_TOKEN")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://router.huggingface.co/v1")
GEN_MODEL       = os.getenv("GEN_MODEL")

EMB_BACKEND     = os.getenv("EMBEDDINGS_BACKEND", "local")
EMB_MODEL       = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB   = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD")

client = OpenAI(base_url=OPENAI_BASE_URL, api_key=HF_TOKEN)

# Optional local embeddings - temporarily disabled for testing
# if EMB_BACKEND == "local":
#     from sentence_transformers import SentenceTransformer
#     emb_model = SentenceTransformer(EMB_MODEL)

# Temporarily use mock embeddings for testing
emb_model = None

app = FastAPI(title="GentleOmega Orchestrator")

# --- PostgreSQL connection ---
pg = connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)

DIM = 384 if EMB_BACKEND == "local" and "MiniLM" in EMB_MODEL else 1536


class AskPayload(BaseModel):
    user_id: str = "aamir"
    agent: str = "chat"
    query: str
    goal: str | None = None
    k: int = 10


# --- Embedding utility ---
def embed_text(text: str) -> List[float]:
    # Temporarily return mock embeddings for testing
    if EMB_BACKEND == "local":
        # Return a fixed-size mock embedding vector
        return [0.1] * 384
    else:
        e = client.embeddings.create(model=EMB_MODEL, input=text)
        return e.data[0].embedding


# --- Memory upsert ---
def upsert_memory(agent: str, user_id: str, source: str, content: str,
                  meta: Dict[str, Any] | None = None, importance: float = 0.3):
    if pg is None:
        print(f"[Mock] Upsert memory for {agent}/{user_id}: {content[:50]}...")
        return
    
    vec = embed_text(content)
    with pg.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memories(agent,user_id,source,content,meta,embedding,importance)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (agent, user_id, source, content, meta or {}, vec, importance)
        )


# --- Retrieve context ---
def retrieve(agent: str, user_id: str, query: str, k: int = 10) -> List[str]:
    if pg is None:
        print(f"[Mock] Retrieve context for {agent}/{user_id}: {query[:30]}...")
        return [f"Mock context for: {query}"]
    
    q = embed_text(query)
    with pg.cursor() as cur:
        cur.execute(
            """
            WITH scored AS (
              SELECT content,
                     0.60 * (1 - (embedding <=> %s)) AS sim,
                     0.15 * importance AS imp,
                     0.25 * GREATEST(0, 30 - EXTRACT(EPOCH FROM (now()-recency))/86400.0) * 0.01 AS rec
              FROM memories
              WHERE user_id=%s AND agent=%s
              ORDER BY (0.60 * (1 - (embedding <=> %s))
                        + 0.15*importance
                        + 0.25 * GREATEST(0, 30 - EXTRACT(EPOCH FROM (now()-recency))/86400.0) * 0.01) DESC
              LIMIT %s
            )
            SELECT content FROM scored;
            """,
            (q, user_id, agent, q, k)
        )
        rows = cur.fetchall()
        return [r[0] for r in rows]


# --- Generate ---
def generate(messages: List[Dict[str, str]]) -> str:
    # For testing without API, return a mock response
    if not HF_TOKEN or HF_TOKEN == "REPLACE_WITH_YOUR_HF_TOKEN":
        return "Mock response: This is a test response since no valid API token is configured."
    
    resp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=messages,
        temperature=0.4,
    )
    return resp.choices[0].message.content


# --- Live session loop ---
def live_session(user_id: str, agent: str, goal: str, seconds: int = 300):
    session = str(uuid.uuid4())
    start = time.time()
    upsert_memory(agent, user_id, "system", f"SESSION {session} GOAL: {goal}", {"session": session}, 0.9)
    turn = 0
    while time.time() - start < seconds:
        turn += 1
        ctx = "\n\n".join(retrieve(agent, user_id, goal, k=10))
        messages = [
            {"role": "system", "content": "You are GentleOmega Orchestrator. Reflect on impact; use memory; end with Next-Actions."},
            {"role": "user", "content": f"Goal: {goal}\nContext:\n{ctx}\nTurn:{turn}"}
        ]
        out = generate(messages)
        upsert_memory(agent, user_id, "assistant", out, {"session": session, "turn": turn}, 0.6)
        if "DONE" in out or turn >= 12:
            break
    return {"session": session, "turns": turn}


# --- FastAPI endpoints ---
@app.post("/ask")
def ask(p: AskPayload):
    ctx = retrieve(p.agent, p.user_id, p.query, k=p.k)
    messages = [
        {"role": "system", "content": "Use retrieved context. If missing, ask for specific data needed."},
        {"role": "user", "content": f"Query: {p.query}\nContext:\n" + "\n".join(ctx)}
    ]
    answer = generate(messages)
    upsert_memory(p.agent, p.user_id, "assistant", answer, {"query": p.query}, 0.5)
    return {"answer": answer, "used_context": ctx}


@app.post("/live")
def live(p: AskPayload):
    goal = p.goal or p.query
    return live_session(p.user_id, p.agent, goal, seconds=300)


@app.post("/embed")
async def embed(text: str, background_tasks: BackgroundTasks):
    """Generate embeddings for input text with blockchain PoD/PoE"""
    # Record PoD
    pod_data = {
        "operation": "embed",
        "input_text": text,
        "timestamp": time.time(),
        "model": EMB_MODEL
    }
    
    pod_result = await record_pod(pod_data)
    
    # Generate embedding
    start_time = time.time()
    embedding = embed_text(text)
    processing_time = time.time() - start_time
    
    # Prepare execution result
    execution_result = {
        "status": "completed",
        "embedding_size": len(embedding),
        "processing_time": processing_time,
        "model": EMB_MODEL,
        "backend": EMB_BACKEND
    }
    
    # Record PoE in background
    if pod_result.get("status") == "success":
        background_tasks.add_task(
            record_poe, 
            pod_result["pod_hash"], 
            execution_result
        )
    
    return {
        "embedding": embedding, 
        "dim": len(embedding),
        "blockchain": {
            "pod_hash": pod_result.get("pod_hash"),
            "transaction_hash": pod_result.get("transaction_hash"),
            "status": pod_result.get("status")
        }
    }


@app.post("/items")
async def create_item(content: str, user_id: str = "default"):
    """Create new item with blockchain PoD tracking"""
    try:
        with pg.cursor() as cur:
            cur.execute(
                "INSERT INTO items (content, user_id, created_at) VALUES (%s, %s, NOW()) RETURNING id, created_at",
                (content, user_id)
            )
            result = cur.fetchone()
            item_id, created_at = result
        
        return {
            "status": "success",
            "item_id": item_id,
            "content": content,
            "user_id": user_id,
            "created_at": created_at.isoformat(),
            "message": "Item created - blockchain PoD/PoE will be processed automatically"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/items/{item_id}")
async def get_item(item_id: int, background_tasks: BackgroundTasks):
    """Retrieve item with blockchain PoE tracking"""
    try:
        # Record PoD for retrieval
        pod_data = {
            "operation": "retrieve",
            "item_id": item_id,
            "timestamp": time.time()
        }
        
        pod_result = await record_pod(pod_data)
        
        # Get item from database
        start_time = time.time()
        with pg.cursor() as cur:
            cur.execute(
                "SELECT id, content, user_id, created_at FROM items WHERE id = %s",
                (item_id,)
            )
            result = cur.fetchone()
        
        processing_time = time.time() - start_time
        
        if result:
            item_id, content, user_id, created_at = result
            
            # Prepare execution result
            execution_result = {
                "status": "found",
                "processing_time": processing_time,
                "item_exists": True
            }
            
            # Record PoE in background
            if pod_result.get("status") == "success":
                background_tasks.add_task(
                    record_poe,
                    pod_result["pod_hash"],
                    execution_result
                )
            
            return {
                "status": "success",
                "item": {
                    "id": item_id,
                    "content": content,
                    "user_id": user_id,
                    "created_at": created_at.isoformat()
                },
                "blockchain": {
                    "pod_hash": pod_result.get("pod_hash"),
                    "transaction_hash": pod_result.get("transaction_hash")
                }
            }
        else:
            # Record PoE for not found
            execution_result = {
                "status": "not_found",
                "processing_time": processing_time,
                "item_exists": False
            }
            
            if pod_result.get("status") == "success":
                background_tasks.add_task(
                    record_poe,
                    pod_result["pod_hash"],
                    execution_result
                )
            
            return {
                "status": "not_found",
                "message": "Item not found",
                "blockchain": {
                    "pod_hash": pod_result.get("pod_hash"),
                    "transaction_hash": pod_result.get("transaction_hash")
                }
            }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/health")
def health():
    return {"status": "ok", "dim": DIM, "blockchain": "enabled"}


# Shutdown handler for blockchain client cleanup
@app.on_event("shutdown")
async def shutdown_event():
    await cleanup_blockchain_client()
