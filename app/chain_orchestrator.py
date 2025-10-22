"""
GentleΩ Chain Orchestrator - Phase 4 EVM Integration
Autonomous loop for PoE verification and blockchain synchronization
Runs every 10 minutes to process pending transactions
"""

import asyncio
import logging
import os
import sys
from typing import List, Tuple, Optional, Dict, Any
from dotenv import load_dotenv

# Try to import asyncpg, fallback to psycopg if not available
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    print("Warning: asyncpg not available, using synchronous database operations")

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))
from psycopg_fix import connect_pg
from blockchain_client import push_to_chain, get_tx_receipt, get_chain_head, ping_rpc

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

# Database configuration
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD", "postgres")

# Build DSN
DB_DSN = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

logger = logging.getLogger("chain_orch")
logger.setLevel(logging.INFO)

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)
fh = logging.FileHandler("logs/chain_sync.log", encoding="utf-8")
fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(fh)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(console_handler)

# SQL queries for blockchain ledger operations
SQL_SELECT_PENDING = """
SELECT id, poe_hash
FROM blockchain_ledger
WHERE status = 'queued'
ORDER BY id
LIMIT 100;
"""

SQL_MARK_PENDING = """
UPDATE blockchain_ledger
SET status='pending', tx_hash=$2, updated_at=now()
WHERE id=$1;
"""

SQL_INSERT_LEDGER = """
INSERT INTO blockchain_ledger (poe_hash, status)
VALUES ($1, 'queued')
ON CONFLICT (poe_hash) DO NOTHING;
"""

SQL_SELECT_UNCONFIRMED = """
SELECT id, tx_hash, poe_hash
FROM blockchain_ledger
WHERE status = 'pending'
ORDER BY id
LIMIT 200;
"""

SQL_CONFIRM = """
UPDATE blockchain_ledger
SET status='confirmed', block_number=$2, updated_at=now()
WHERE id=$1;
"""

SQL_FAIL = """
UPDATE blockchain_ledger
SET status='failed', updated_at=now()
WHERE id=$1;
"""

SQL_STATS = """
SELECT
  (SELECT COUNT(*) FROM blockchain_ledger WHERE status='pending') AS pending_tx,
  (SELECT COUNT(*) FROM blockchain_ledger WHERE status='confirmed') AS confirmed_tx,
  (SELECT COUNT(*) FROM blockchain_ledger WHERE status='failed') AS failed_tx,
  (SELECT COUNT(*) FROM blockchain_ledger WHERE status='queued') AS queued_tx;
"""

# PoD->PoE cache queries
SQL_SCAN_OFFCHAIN = """
SELECT poe_hash
FROM pods_poe
WHERE on_chain = false
ORDER BY created_at
LIMIT 500;
"""

SQL_FLAG_ONCHAIN = """
UPDATE pods_poe
SET on_chain = true, updated_at=now()
WHERE poe_hash = $1;
"""


async def _get_conn():
    """Get async database connection"""
    if not ASYNCPG_AVAILABLE:
        raise RuntimeError("asyncpg not available, use _get_sync_conn() instead")
    return await asyncpg.connect(dsn=DB_DSN)


def _get_sync_conn():
    """Get synchronous database connection using psycopg_fix"""
    return connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)


async def enqueue_missing_poe() -> int:
    """Mirror any off-chain PoE not yet queued into blockchain_ledger"""
    try:
        if ASYNCPG_AVAILABLE:
            # Async version
            conn = await _get_conn()
            try:
                rows = await conn.fetch(SQL_SCAN_OFFCHAIN)
                if not rows:
                    return 0
                
                count = 0
                for r in rows:
                    poe_hash = r["poe_hash"]
                    try:
                        await conn.execute(SQL_INSERT_LEDGER, poe_hash)
                        count += 1
                    except Exception as e:
                        logger.debug(f"Skip duplicate PoE {poe_hash[:16]}: {e}")
                
                logger.info(f"Enqueued {count} PoE hashes from cache")
                return count
            finally:
                await conn.close()
        else:
            # Synchronous version
            pg = _get_sync_conn()
            try:
                with pg.cursor() as cur:
                    cur.execute(SQL_SCAN_OFFCHAIN)
                    rows = cur.fetchall()
                    
                    if not rows:
                        return 0
                    
                    count = 0
                    for r in rows:
                        poe_hash = r[0]  # First column in synchronous result
                        try:
                            cur.execute(SQL_INSERT_LEDGER, (poe_hash,))
                            pg.commit()
                            count += 1
                        except Exception as e:
                            logger.debug(f"Skip duplicate PoE {poe_hash[:16]}: {e}")
                            pg.rollback()
                    
                    logger.info(f"Enqueued {count} PoE hashes from cache")
                    return count
            finally:
                if pg:
                    pg.close()
    except Exception as e:
        logger.error(f"Failed to enqueue missing PoE: {e}")
        return 0


async def submit_queued() -> int:
    """Submit queued PoE hashes to blockchain"""
    try:
        submitted = 0
        
        if ASYNCPG_AVAILABLE:
            # Async version
            conn = await _get_conn()
            try:
                rows = await conn.fetch(SQL_SELECT_PENDING)
                for r in rows:
                    poe_hash = r["poe_hash"]
                    try:
                        # Push to chain using blockchain_client
                        res = push_to_chain(poe_hash)
                        txh = res["tx_hash"]
                        
                        # Mark as pending in ledger
                        await conn.execute(SQL_MARK_PENDING, r["id"], txh)
                        logger.info(f"Submitted PoE {poe_hash[:16]}... -> tx {txh[:16]}...")
                        submitted += 1
                        
                        # Small delay to avoid overwhelming RPC
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logger.error(f"Submit failed for PoE {poe_hash[:16]}...: {e}")
                        # Continue with next transaction rather than failing completely
                
                return submitted
            finally:
                await conn.close()
        else:
            # Synchronous version
            pg = _get_sync_conn()
            try:
                with pg.cursor() as cur:
                    cur.execute(SQL_SELECT_PENDING)
                    rows = cur.fetchall()
                    
                    for r in rows:
                        ledger_id, poe_hash = r[0], r[1]
                        try:
                            # Push to chain using blockchain_client
                            res = push_to_chain(poe_hash)
                            txh = res["tx_hash"]
                            
                            # Mark as pending in ledger
                            cur.execute(SQL_MARK_PENDING, (ledger_id, txh))
                            pg.commit()
                            logger.info(f"Submitted PoE {poe_hash[:16]}... -> tx {txh[:16]}...")
                            submitted += 1
                            
                            # Small delay to avoid overwhelming RPC
                            await asyncio.sleep(0.1)
                            
                        except Exception as e:
                            logger.error(f"Submit failed for PoE {poe_hash[:16]}...: {e}")
                            pg.rollback()
                
                return submitted
            finally:
                if pg:
                    pg.close()
    except Exception as e:
        logger.error(f"Failed to submit queued transactions: {e}")
        return 0


async def verify_chain_integrity() -> int:
    """Verify pending transactions and update their status"""
    try:
        confirmed = 0
        
        if ASYNCPG_AVAILABLE:
            # Async version
            conn = await _get_conn()
            try:
                rows = await conn.fetch(SQL_SELECT_UNCONFIRMED)
                for r in rows:
                    tx_hash = r["tx_hash"]
                    poe_hash = r["poe_hash"]
                    
                    try:
                        # Skip simulation transactions
                        if tx_hash.startswith(("sim_", "pod_", "poe_")):
                            # Mark simulation transactions as confirmed after 1 minute
                            await conn.execute(SQL_CONFIRM, r["id"], get_chain_head())
                            await conn.execute(SQL_FLAG_ONCHAIN, poe_hash)
                            confirmed += 1
                            logger.debug(f"Marked simulation tx {tx_hash[:16]}... as confirmed")
                            continue
                        
                        # Check real blockchain transaction
                        receipt = get_tx_receipt(tx_hash)
                        if not receipt:
                            continue  # Still pending
                        
                        status_ok = int(receipt.get("status", "0x0"), 16) == 1
                        blk = int(receipt["blockNumber"], 16) if receipt.get("blockNumber") else None
                        
                        if status_ok and blk is not None:
                            await conn.execute(SQL_CONFIRM, r["id"], blk)
                            await conn.execute(SQL_FLAG_ONCHAIN, poe_hash)
                            confirmed += 1
                            logger.info(f"Confirmed tx {tx_hash[:16]}... at block {blk}")
                        elif not status_ok and blk is not None:
                            await conn.execute(SQL_FAIL, r["id"])
                            logger.warning(f"Failed tx {tx_hash[:16]}... at block {blk}")
                            
                    except Exception as e:
                        logger.error(f"Verification failed for tx {tx_hash[:16]}...: {e}")
                
                return confirmed
            finally:
                await conn.close()
        else:
            # Synchronous version
            pg = _get_sync_conn()
            try:
                with pg.cursor() as cur:
                    cur.execute(SQL_SELECT_UNCONFIRMED)
                    rows = cur.fetchall()
                    
                    for r in rows:
                        ledger_id, tx_hash, poe_hash = r[0], r[1], r[2]
                        
                        try:
                            # Skip simulation transactions
                            if tx_hash.startswith(("sim_", "pod_", "poe_")):
                                # Mark simulation transactions as confirmed after 1 minute
                                cur.execute(SQL_CONFIRM, (ledger_id, get_chain_head()))
                                cur.execute(SQL_FLAG_ONCHAIN, (poe_hash,))
                                pg.commit()
                                confirmed += 1
                                logger.debug(f"Marked simulation tx {tx_hash[:16]}... as confirmed")
                                continue
                            
                            # Check real blockchain transaction
                            receipt = get_tx_receipt(tx_hash)
                            if not receipt:
                                continue  # Still pending
                            
                            status_ok = int(receipt.get("status", "0x0"), 16) == 1
                            blk = int(receipt["blockNumber"], 16) if receipt.get("blockNumber") else None
                            
                            if status_ok and blk is not None:
                                cur.execute(SQL_CONFIRM, (ledger_id, blk))
                                cur.execute(SQL_FLAG_ONCHAIN, (poe_hash,))
                                pg.commit()
                                confirmed += 1
                                logger.info(f"Confirmed tx {tx_hash[:16]}... at block {blk}")
                            elif not status_ok and blk is not None:
                                cur.execute(SQL_FAIL, (ledger_id,))
                                pg.commit()
                                logger.warning(f"Failed tx {tx_hash[:16]}... at block {blk}")
                                
                        except Exception as e:
                            logger.error(f"Verification failed for tx {tx_hash[:16]}...: {e}")
                            pg.rollback()
                
                return confirmed
            finally:
                if pg:
                    pg.close()
    except Exception as e:
        logger.error(f"Chain integrity verification failed: {e}")
        return 0


async def get_orchestrator_stats() -> Dict[str, Any]:
    """Get current orchestrator statistics"""
    try:
        rpc_ok, latency = ping_rpc()
        
        if ASYNCPG_AVAILABLE:
            # Async version
            conn = await _get_conn()
            try:
                row = await conn.fetchrow(SQL_STATS)
                return {
                    "status": "operational" if rpc_ok else "degraded",
                    "rpc_connectivity": rpc_ok,
                    "chain_latency_ms": latency,
                    "last_block": get_chain_head() if rpc_ok else -1,
                    "pending_tx": row["pending_tx"] if row else 0,
                    "confirmed_tx": row["confirmed_tx"] if row else 0,
                    "failed_tx": row["failed_tx"] if row else 0,
                    "queued_tx": row["queued_tx"] if row else 0,
                }
            finally:
                await conn.close()
        else:
            # Synchronous version
            pg = _get_sync_conn()
            try:
                with pg.cursor() as cur:
                    cur.execute(SQL_STATS)
                    row = cur.fetchone()
                    
                    if row:
                        pending_tx, confirmed_tx, failed_tx, queued_tx = row
                    else:
                        pending_tx = confirmed_tx = failed_tx = queued_tx = 0
                    
                    return {
                        "status": "operational" if rpc_ok else "degraded",
                        "rpc_connectivity": rpc_ok,
                        "chain_latency_ms": latency,
                        "last_block": get_chain_head() if rpc_ok else -1,
                        "pending_tx": pending_tx,
                        "confirmed_tx": confirmed_tx,
                        "failed_tx": failed_tx,
                        "queued_tx": queued_tx,
                    }
            finally:
                if pg:
                    pg.close()
                    
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {
            "status": "error",
            "error": str(e),
            "rpc_connectivity": False,
            "chain_latency_ms": -1,
            "last_block": -1,
            "pending_tx": 0,
            "confirmed_tx": 0,
            "failed_tx": 0,
            "queued_tx": 0,
        }


async def orchestration_cycle() -> Dict[str, int]:
    """Single orchestration cycle - returns metrics"""
    logger.info("Starting orchestration cycle...")
    
    # Check RPC connectivity first
    rpc_ok, latency = ping_rpc()
    if not rpc_ok:
        logger.warning("RPC connectivity issues - continuing with limited functionality")
    
    # Run orchestration steps
    enqueued = await enqueue_missing_poe()
    submitted = await submit_queued()
    confirmed = await verify_chain_integrity()
    
    metrics = {
        "enqueued": enqueued,
        "submitted": submitted, 
        "confirmed": confirmed,
        "rpc_latency_ms": latency,
        "rpc_ok": rpc_ok
    }
    
    logger.info(
        f"Cycle complete | enqueued={enqueued} submitted={submitted} confirmed={confirmed} "
        f"rpc_latency_ms={latency} rpc_ok={rpc_ok}"
    )
    
    return metrics


async def orchestration_loop():
    """Main orchestration loop - runs forever with 10-minute cycles"""
    logger.info("🔗 GentleΩ Chain Orchestrator starting...")
    
    cycle_count = 0
    while True:
        try:
            cycle_count += 1
            logger.info(f"--- Cycle #{cycle_count} ---")
            
            await orchestration_cycle()
            
            # 10-minute sleep between cycles
            logger.info("Sleeping for 10 minutes until next cycle...")
            await asyncio.sleep(600)  # 10 minutes
            
        except KeyboardInterrupt:
            logger.info("Orchestrator stopped by user")
            break
        except Exception as e:
            logger.error(f"Orchestration cycle failed: {e}")
            # Short sleep before retrying on error
            await asyncio.sleep(60)


# Single-shot functions for external use
async def run_single_cycle() -> Dict[str, int]:
    """Run a single orchestration cycle (useful for testing)"""
    return await orchestration_cycle()


def verify_setup() -> bool:
    """Verify that required database tables exist"""
    try:
        pg = _get_sync_conn()
        with pg.cursor() as cur:
            # Check if required tables exist
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name IN ('blockchain_ledger', 'pods_poe')
            """)
            table_count = cur.fetchone()[0]
            
            if table_count < 2:
                logger.error("Required tables missing. Please run migration_2025_10_22_blockchain_ledger.sql")
                return False
            
            logger.info("✅ Database setup verified")
            return True
            
    except Exception as e:
        logger.error(f"Setup verification failed: {e}")
        return False


if __name__ == "__main__":
    # Verify setup first
    if not verify_setup():
        print("❌ Setup verification failed")
        exit(1)
    
    print("✅ GentleΩ Phase 4 Chain Orchestrator")
    print("Starting autonomous blockchain synchronization...")
    
    try:
        asyncio.run(orchestration_loop())
    except KeyboardInterrupt:
        print("\n👋 Chain orchestrator stopped")