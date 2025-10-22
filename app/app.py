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

# Import orchestration system
from orchestrator import start_orchestration, stop_orchestration, submit_create_item_task, get_orchestration_health

# Import chain orchestrator
from chain_orchestrator import get_orchestrator_stats, run_single_cycle

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

HF_TOKEN        = os.getenv("HF_TOKEN")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://router.huggingface.co/v1")
GEN_MODEL       = os.getenv("GEN_MODEL")

EMB_BACKEND     = os.getenv("EMBEDDINGS_BACKEND", "local")
EMB_MODEL       = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB   = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD")

# Guard OpenAI client init - don't crash if tokens missing
client = None
api_key = HF_TOKEN or OPENAI_API_KEY
if api_key and api_key != "REPLACE_WITH_YOUR_HF_TOKEN":
    try:
        client = OpenAI(base_url=OPENAI_BASE_URL, api_key=api_key)
        print("✅ OpenAI client initialized successfully")
    except Exception as e:
        print(f"⚠️  OpenAI client initialization failed: {e}")
        client = None
else:
    print("⚠️  No valid API token found - LLM functionality disabled")

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
    # Return mock embeddings for testing or when no client available
    if EMB_BACKEND == "local" or not client:
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
    if not client:
        return "Mock response: This is a test response since no valid API token is configured."
    
    try:
        resp = client.chat.completions.create(
            model=GEN_MODEL,
            messages=messages,
            temperature=0.4,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error generating response: {str(e)}"


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
async def create_item(content: str, user_id: str = "default", use_orchestration: bool = False):
    """Create new item with optional orchestration and blockchain PoD tracking"""
    if use_orchestration:
        # Use orchestration system for background processing
        task_id = submit_create_item_task(content, user_id)
        return {
            "status": "submitted",
            "task_id": task_id,
            "content": content,
            "user_id": user_id,
            "message": "Item creation submitted to orchestration system",
            "orchestrated": True
        }
    else:
        # Direct creation (legacy mode)
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
                "message": "Item created directly",
                "orchestrated": False
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
async def health():
    orchestration_health = get_orchestration_health()
    chain_stats = await get_orchestrator_stats()
    
    return {
        "status": "ok", 
        "dim": DIM, 
        "blockchain": "enabled",
        "orchestration": orchestration_health,
        "components": {
            "rpc_connectivity": chain_stats.get("rpc_connectivity", False),
            "chain_latency_ms": chain_stats.get("chain_latency_ms", -1),
            "last_block": chain_stats.get("last_block", -1)
        }
    }

@app.get("/orchestration/status")
def orchestration_status():
    """Get detailed orchestration status"""
    return get_orchestration_health()

@app.post("/orchestration/task")
def submit_orchestration_task(content: str, user_id: str = "default"):
    """Submit task through orchestration system"""
    task_id = submit_create_item_task(content, user_id)
    return {
        "status": "submitted",
        "task_id": task_id,
        "message": "Task submitted for orchestrated processing"
    }


@app.get("/chain/status")
async def chain_status():
    """Get blockchain integration status - Phase 4 endpoint"""
    stats = await get_orchestrator_stats()
    
    return {
        "status": stats.get("status", "unknown"),
        "last_block": stats.get("last_block", -1),
        "pending_tx": stats.get("pending_tx", 0),
        "verified": stats.get("confirmed_tx", 0),
        "failed_tx": stats.get("failed_tx", 0),
        "queued_tx": stats.get("queued_tx", 0),
        "rpc_latency_ms": stats.get("chain_latency_ms", -1),
        "rpc_ok": stats.get("rpc_connectivity", False)
    }


@app.post("/chain/cycle")
async def trigger_chain_cycle():
    """Manually trigger a single chain orchestration cycle"""
    try:
        metrics = await run_single_cycle()
        return {
            "status": "success",
            "message": "Chain cycle completed successfully",
            "metrics": metrics
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Chain cycle failed: {str(e)}"
        }


@app.get("/logs/recent")
async def get_recent_logs(lines: int = 50):
    """Get recent lines from chain sync log"""
    try:
        log_file = "logs/chain_sync.log"
        if not os.path.exists(log_file):
            return {"logs": [], "message": "Log file not found"}
        
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
        return {
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to read logs: {str(e)}"
        }


@app.get("/chain/ledger")
async def get_blockchain_ledger(limit: int = 100, status_filter: str = None):
    """Get blockchain ledger entries with optional status filtering"""
    try:
        with pg.cursor() as cur:
            if status_filter:
                cur.execute("""
                    SELECT id, poe_hash, tx_hash, block_number, status, created_at, updated_at
                    FROM blockchain_ledger 
                    WHERE status = %s
                    ORDER BY updated_at DESC 
                    LIMIT %s
                """, (status_filter, limit))
            else:
                cur.execute("""
                    SELECT id, poe_hash, tx_hash, block_number, status, created_at, updated_at
                    FROM blockchain_ledger 
                    ORDER BY updated_at DESC 
                    LIMIT %s
                """, (limit,))
            
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            
            ledger_entries = []
            for row in rows:
                entry = dict(zip(columns, row))
                # Convert timestamps to ISO format
                if entry['created_at']:
                    entry['created_at'] = entry['created_at'].isoformat()
                if entry['updated_at']:
                    entry['updated_at'] = entry['updated_at'].isoformat()
                ledger_entries.append(entry)
            
        return {
            "ledger": ledger_entries,
            "count": len(ledger_entries),
            "filter": status_filter
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch ledger: {str(e)}"
        }


@app.get("/chain/metrics")
async def get_chain_metrics():
    """Get detailed chain metrics for dashboard"""
    try:
        with pg.cursor() as cur:
            # Get status counts
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM blockchain_ledger 
                GROUP BY status
            """)
            status_counts = {row[0]: row[1] for row in cur.fetchall()}
            
            # Get latest confirmed block
            cur.execute("""
                SELECT MAX(block_number) as last_confirmed_block
                FROM blockchain_ledger 
                WHERE status = 'confirmed' AND block_number IS NOT NULL
            """)
            result = cur.fetchone()
            last_confirmed_block = result[0] if result and result[0] else -1
            
            # Get total ledger count
            cur.execute("SELECT COUNT(*) FROM blockchain_ledger")
            ledger_total = cur.fetchone()[0]
            
            # Get last update timestamp
            cur.execute("""
                SELECT MAX(updated_at) as last_updated
                FROM blockchain_ledger
            """)
            result = cur.fetchone()
            last_updated = result[0].isoformat() if result and result[0] else None
        
        # Get RPC connectivity
        from chain_orchestrator import ping_rpc, get_chain_head
        rpc_ok, latency = ping_rpc()
        current_block = get_chain_head() if rpc_ok else -1
        
        return {
            "status_counts": status_counts,
            "last_confirmed_block": last_confirmed_block,
            "current_block": current_block,
            "ledger_total": ledger_total,
            "last_updated": last_updated,
            "rpc_connectivity": rpc_ok,
            "rpc_latency_ms": latency,
            "blockchain_synced": current_block == last_confirmed_block if current_block > 0 else False
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get metrics: {str(e)}"
        }


# Startup handler for orchestration system
@app.on_event("startup")
async def startup_event():
    """Initialize orchestration system on app startup"""
    try:
        await start_orchestration()
        print("✅ GentleOmega Orchestration System started successfully")
        
        # Start background chain orchestrator
        from chain_orchestrator import orchestration_loop
        asyncio.create_task(orchestration_loop())
        print("🔗 GentleOmega Chain Orchestrator started in background")
        
        # Check chain connectivity 
        chain_stats = await get_orchestrator_stats()
        if chain_stats.get("rpc_connectivity"):
            print(f"✅ GentleΩ Phase 4 Live Blockchain Integration Operational")
            print(f"   📊 Chain: Block {chain_stats.get('last_block', 'N/A')}, Latency: {chain_stats.get('chain_latency_ms', 'N/A')}ms")
        else:
            print("⚠️  GentleΩ Phase 4 running in simulation mode (no RPC connectivity)")
            
    except Exception as e:
        print(f"Warning: System startup error: {e}")

# Shutdown handler for cleanup
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on app shutdown"""
    try:
        await stop_orchestration()
        await cleanup_blockchain_client()
        print("👋 GentleΩ systems shutdown complete")
    except Exception as e:
        print(f"Warning: Shutdown error: {e}")
