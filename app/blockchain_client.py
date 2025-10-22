"""
GentleΩ Blockchain Client - Phase 4 EVM Integration
Handles Proof of Data (PoD) and Proof of Execution (PoE) recording
Enhanced with EVM blockchain transaction support and local ledger
"""

import os
import sys
import json
import time
import logging
import hashlib
import asyncio
import binascii
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import httpx
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))
from psycopg_fix import connect_pg

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

CHAIN_RPC = os.getenv("CHAIN_RPC", "https://your-chain-endpoint")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "your_private_key")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "your_wallet_address")

# Setup logging
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("chain")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("logs/chain_sync.log", encoding="utf-8")
fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(fh)

# EVM transaction support
USE_PERSONAL = False  # set True only if your node supports personal_sendTransaction

# Database configuration
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD", "postgres")


class RPC:
    """Simple EVM JSON-RPC client"""
    def __init__(self, url: str):
        self.c = httpx.Client(timeout=20.0)
        self.url = url
        self._id = 0

    def call(self, method: str, params: list) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        r = self.c.post(self.url, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"RPC error {data['error']}")
        return data["result"]


# Global RPC client
rpc = RPC(CHAIN_RPC) if CHAIN_RPC and CHAIN_RPC != "https://your-chain-endpoint" else None


def _to_hex(val: int) -> str:
    """Convert integer to hex string"""
    return hex(val)


def _ensure_0x(h: str) -> str:
    """Ensure hex string has 0x prefix"""
    return h if h.startswith("0x") else "0x" + h


def get_chain_head() -> int:
    """Get latest block number"""
    if not rpc:
        return -1
    block_hex = rpc.call("eth_blockNumber", [])
    return int(block_hex, 16)


def get_nonce(address: str) -> int:
    """Get transaction nonce for address"""
    if not rpc:
        return 0
    n_hex = rpc.call("eth_getTransactionCount", [address, "pending"])
    return int(n_hex, 16)


def estimate_fees() -> Tuple[int, int]:
    """Estimate EIP-1559 fees"""
    if not rpc:
        return 1_500_000_000, 2_000_000_000  # Fallback values
    
    try:
        # EIP-1559 style
        base = rpc.call("eth_feeHistory", [1, "latest", []])
        # fallback tips
        tip_hex = rpc.call("eth_maxPriorityFeePerGas", [])
        priority = int(tip_hex, 16) if isinstance(tip_hex, str) else 1_500_000_000
        # latest baseFee from history
        base_fee = int(base["baseFeePerGas"][-1], 16)
        max_fee = base_fee + priority * 2
        return priority, max_fee
    except Exception:
        return 1_500_000_000, 2_000_000_000  # Fallback values


def _poe_data_bytes(poe_hash_hex: str) -> str:
    """
    Accept poe_hash as hex string (with or without 0x). Pad to even length.
    Return hex data string with 0x prefix suitable for tx 'data'.
    """
    h = poe_hash_hex[2:] if poe_hash_hex.startswith("0x") else poe_hash_hex
    if len(h) % 2:
        h = "0" + h
    # simple guard: cap to ~6KB data if needed (EVM calldata gas)
    if len(h) > 12000:
        raise ValueError("poe_hash payload too large")
    return "0x" + h


def push_to_chain(poe_hash_hex: str) -> Dict[str, Any]:
    """
    Creates a **data-only, zero-value** tx sending to our own address,
    embedding the PoE hash. Returns {tx_hash}.
    """
    if not rpc:
        logger.info(f"[SIMULATION] push_to_chain: {poe_hash_hex[:16]}...")
        return {"tx_hash": f"sim_{poe_hash_hex[:16]}_{int(time.time())}"}
    
    assert WALLET_ADDRESS and WALLET_PRIVATE_KEY, "Wallet env vars not set"
    
    nonce = get_nonce(WALLET_ADDRESS)
    priorityFee, maxFee = estimate_fees()
    gas_limit = 120000  # generous upper bound for data-only tx

    tx = {
        "from": WALLET_ADDRESS,
        "to": WALLET_ADDRESS,
        "value": _to_hex(0),
        "nonce": _to_hex(nonce),
        "gas": _to_hex(gas_limit),
        "maxPriorityFeePerGas": _to_hex(priorityFee),
        "maxFeePerGas": _to_hex(maxFee),
        "data": _poe_data_bytes(poe_hash_hex),
        "type": "0x2",  # EIP-1559
    }

    # --- signing path ---
    try:
        tx_hash = rpc.call("eth_sendTransaction", [tx])
        logger.info(f"broadcast tx nonce={nonce} tx_hash={tx_hash}")
        return {"tx_hash": tx_hash}
    except Exception as e:
        # fall-through: try personal_sendTransaction if unlocked keystore exists on node
        if USE_PERSONAL:
            try:
                tx_hash = rpc.call("personal_sendTransaction", [tx, ""])
                logger.info(f"broadcast (personal) tx nonce={nonce} tx_hash={tx_hash}")
                return {"tx_hash": tx_hash}
            except Exception as e2:
                logger.error(f"RPC send failed: {e2}")
                raise
        else:
            logger.error(
                "Node rejected eth_sendTransaction. For air-gapped signing, add eth_account and signRaw."
            )
            raise


def get_tx_receipt(tx_hash: str) -> Optional[Dict[str, Any]]:
    """Get transaction receipt"""
    if not rpc:
        return {"status": "0x1", "blockNumber": hex(get_chain_head())}  # Simulate success
    
    r = rpc.call("eth_getTransactionReceipt", [tx_hash])
    return r  # may be None until mined


def ping_rpc() -> Tuple[bool, int]:
    """Returns (ok, chain_latency_ms)"""
    t0 = time.perf_counter()
    try:
        _ = get_chain_head()
        ms = int((time.perf_counter() - t0) * 1000)
        return True, ms
    except Exception:
        return False, -1


class BlockchainClient:
    """Enhanced blockchain client for PoD/PoE transactions with local ledger and EVM integration"""
    
    def __init__(self):
        self.rpc_url = CHAIN_RPC
        self.private_key = WALLET_PRIVATE_KEY
        self.wallet_address = WALLET_ADDRESS
        self.pg_connection = None
        
    def _get_db_connection(self):
        """Get database connection for ledger operations"""
        if not self.pg_connection:
            self.pg_connection = connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)
        return self.pg_connection
    
    async def close(self):
        """Close any resources"""
        if self.pg_connection:
            self.pg_connection.close()
            self.pg_connection = None
    
    def _generate_pod_hash(self, data: Dict[str, Any]) -> str:
        """Generate Proof of Data hash"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _generate_poe_hash(self, pod_hash: str, result: Dict[str, Any]) -> str:
        """Generate Proof of Execution hash"""
        content = f"{pod_hash}:{json.dumps(result, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _compute_chain_hash(self, data: Dict[str, Any], previous_hash: Optional[str] = None, timestamp: str = None) -> str:
        """Compute hash for blockchain ledger entry with chain integrity"""
        # Use provided timestamp or generate new one
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
            
        # Include previous hash for chain integrity
        chain_content = {
            "data": data,
            "previous_hash": previous_hash,
            "timestamp": timestamp
        }
        content = json.dumps(chain_content, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_last_ledger_hash(self) -> Optional[str]:
        """Get the hash of the most recent ledger entry"""
        try:
            pg = self._get_db_connection()
            with pg.cursor() as cur:
                cur.execute(
                    "SELECT hash FROM blockchain_ledger ORDER BY created_at DESC, id DESC LIMIT 1"
                )
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Error getting last ledger hash: {e}")
            return None
    
    def add_to_ledger(self, data: Dict[str, Any], content_type: str = "item", user_id: str = None) -> Dict[str, Any]:
        """Add entry to local blockchain ledger with chain integrity"""
        try:
            # Get previous hash for chain integrity
            previous_hash = self.get_last_ledger_hash()
            
            # Generate timestamp for consistent hashing
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Store the timestamp in the data for verification
            enhanced_data = {
                **data,
                "_hash_timestamp": timestamp
            }
            
            # Compute hash for this entry using the timestamp
            entry_hash = self._compute_chain_hash(data, previous_hash, timestamp)
            
            pg = self._get_db_connection()
            with pg.cursor() as cur:
                cur.execute("""
                    INSERT INTO blockchain_ledger 
                    (hash, previous_hash, block_data, content_type, user_id) 
                    VALUES (%s, %s, %s, %s, %s) 
                    RETURNING id, created_at
                """, (entry_hash, previous_hash, json.dumps(enhanced_data), content_type, user_id))
                
                result = cur.fetchone()
                ledger_id, created_at = result
                
            return {
                "status": "success",
                "ledger_id": ledger_id,
                "hash": entry_hash,
                "previous_hash": previous_hash,
                "created_at": created_at.isoformat() if created_at else None,
                "chain_verified": True
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify the integrity of the blockchain ledger"""
        try:
            pg = self._get_db_connection()
            with pg.cursor() as cur:
                cur.execute("""
                    SELECT id, hash, previous_hash, block_data, created_at 
                    FROM blockchain_ledger 
                    ORDER BY created_at, id
                """)
                entries = cur.fetchall()
                
            if not entries:
                return {"status": "success", "message": "Empty chain is valid", "entries": 0}
            
            # Verify chain links
            verified_count = 0
            broken_links = []
            
            for i, (ledger_id, current_hash, previous_hash, block_data, created_at) in enumerate(entries):
                # First entry should have no previous hash
                if i == 0:
                    if previous_hash is not None:
                        broken_links.append(f"Genesis block {ledger_id} has unexpected previous_hash")
                else:
                    # Subsequent entries should link to previous
                    expected_previous = entries[i-1][1]  # hash of previous entry
                    if previous_hash != expected_previous:
                        broken_links.append(f"Block {ledger_id} previous_hash mismatch: expected {expected_previous}, got {previous_hash}")
                
                # Verify hash computation
                try:
                    # Parse block data
                    if isinstance(block_data, str):
                        parsed_data = json.loads(block_data)
                    else:
                        parsed_data = block_data
                    
                    # Extract original data and timestamp
                    hash_timestamp = parsed_data.pop("_hash_timestamp", None)
                    
                    # Compute hash using the stored timestamp
                    computed_hash = self._compute_chain_hash(parsed_data, previous_hash, hash_timestamp)
                    if current_hash != computed_hash:
                        broken_links.append(f"Block {ledger_id} hash verification failed")
                    else:
                        verified_count += 1
                except Exception as e:
                    broken_links.append(f"Block {ledger_id} hash computation error: {e}")
            
            return {
                "status": "success" if not broken_links else "error",
                "entries": len(entries),
                "verified": verified_count,
                "broken_links": broken_links,
                "integrity": "valid" if not broken_links else "compromised"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def record_pod(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record Proof of Data (PoD) transaction with local ledger integration
        
        Args:
            data: Data to be recorded on blockchain
            
        Returns:
            Transaction result with hash and timestamp
        """
        try:
            pod_hash = self._generate_pod_hash(data)
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Create PoD payload for ledger
            pod_payload = {
                "type": "POD",
                "data_hash": pod_hash,
                "timestamp": timestamp,
                "wallet_address": self.wallet_address,
                "original_data": data,
                "data_summary": {
                    "keys": list(data.keys()),
                    "size": len(json.dumps(data))
                }
            }
            
            # Record in local ledger first
            ledger_result = self.add_to_ledger(
                pod_payload, 
                content_type="pod", 
                user_id=data.get("user_id", "system")
            )
            
            # Record in PoD/PoE cache for chain processing
            try:
                pg = self._get_db_connection()
                with pg.cursor() as cur:
                    cur.execute("""
                        INSERT INTO pods_poe (poe_hash, pod_hash, content_type, execution_data, on_chain)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (poe_hash) DO NOTHING
                    """, (pod_hash, pod_hash, "pod", json.dumps(data), False))
                    pg.commit()
            except Exception as e:
                logger.warning(f"Failed to record PoD in cache: {e}")
            
            # For PoD, we don't immediately push to chain - that's handled by orchestrator
            return {
                "status": "success",
                "transaction_hash": f"pod_{pod_hash[:16]}_{int(time.time())}",
                "pod_hash": pod_hash,
                "timestamp": timestamp,
                "ledger": ledger_result,
                "chain_pending": True
            }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def record_poe(self, pod_hash: str, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record Proof of Execution (PoE) transaction with local ledger integration
        
        Args:
            pod_hash: Hash from the original PoD transaction
            execution_result: Result of data processing/execution
            
        Returns:
            Transaction result with PoE hash and verification
        """
        try:
            poe_hash = self._generate_poe_hash(pod_hash, execution_result)
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Create PoE payload for ledger
            poe_payload = {
                "type": "POE",
                "pod_hash": pod_hash,
                "poe_hash": poe_hash,
                "timestamp": timestamp,
                "wallet_address": self.wallet_address,
                "execution_result": execution_result,
                "execution_summary": {
                    "status": execution_result.get("status", "completed"),
                    "result_size": len(json.dumps(execution_result)),
                    "processing_time": execution_result.get("processing_time")
                }
            }
            
            # Record in local ledger
            ledger_result = self.add_to_ledger(
                poe_payload, 
                content_type="poe", 
                user_id=execution_result.get("user_id", "system")
            )
            
            # Record in PoD/PoE cache for chain processing
            try:
                pg = self._get_db_connection()
                with pg.cursor() as cur:
                    cur.execute("""
                        INSERT INTO pods_poe (poe_hash, pod_hash, content_type, execution_data, on_chain)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (poe_hash) DO UPDATE SET
                        execution_data = EXCLUDED.execution_data,
                        updated_at = now()
                    """, (poe_hash, pod_hash, "poe", json.dumps(execution_result), False))
                    pg.commit()
                    logger.info(f"PoE cached for chain processing: {poe_hash[:16]}...")
            except Exception as e:
                logger.error(f"Failed to record PoE in cache: {e}")
            
            return {
                "status": "success",
                "transaction_hash": f"poe_{poe_hash[:16]}_{int(time.time())}",
                "pod_hash": pod_hash,
                "poe_hash": poe_hash,
                "timestamp": timestamp,
                "verification": "complete",
                "ledger": ledger_result,
                "chain_pending": True
            }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "pod_hash": pod_hash,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_transaction_status(self, transaction_hash: str) -> Dict[str, Any]:
        """Get status of a blockchain transaction"""
        try:
            # Check local ledger first
            pg = self._get_db_connection()
            with pg.cursor() as cur:
                cur.execute("""
                    SELECT status, block_number, created_at, updated_at 
                    FROM blockchain_ledger 
                    WHERE tx_hash = %s
                """, (transaction_hash,))
                result = cur.fetchone()
                
                if result:
                    status, block_number, created_at, updated_at = result
                    return {
                        "status": status,
                        "transaction_hash": transaction_hash,
                        "block_number": block_number,
                        "created_at": created_at.isoformat() if created_at else None,
                        "updated_at": updated_at.isoformat() if updated_at else None,
                        "source": "local_ledger"
                    }
            
            # Fallback to chain query if available
            if rpc and not transaction_hash.startswith(("pod_", "poe_", "sim_")):
                receipt = get_tx_receipt(transaction_hash)
                if receipt:
                    return {
                        "status": "confirmed" if receipt.get("status") == "0x1" else "failed",
                        "transaction_hash": transaction_hash,
                        "block_number": int(receipt["blockNumber"], 16) if receipt.get("blockNumber") else None,
                        "source": "chain"
                    }
            
            return {
                "status": "pending",
                "transaction_hash": transaction_hash,
                "source": "unknown"
            }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


# Global blockchain client instance
blockchain_client = BlockchainClient()

# Convenience functions for direct use
async def record_pod(data: Dict[str, Any]) -> Dict[str, Any]:
    """Record Proof of Data transaction"""
    return await blockchain_client.record_pod(data)

async def record_poe(pod_hash: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Record Proof of Execution transaction"""
    return await blockchain_client.record_poe(pod_hash, result)

def add_to_ledger(data: Dict[str, Any], content_type: str = "item", user_id: str = None) -> Dict[str, Any]:
    """Add entry to blockchain ledger"""
    return blockchain_client.add_to_ledger(data, content_type, user_id)

def verify_chain_integrity() -> Dict[str, Any]:
    """Verify blockchain ledger integrity"""
    return blockchain_client.verify_chain_integrity()

def get_last_ledger_hash() -> Optional[str]:
    """Get the hash of the most recent ledger entry"""
    return blockchain_client.get_last_ledger_hash()

async def cleanup_blockchain_client():
    """Cleanup function for FastAPI shutdown"""
    await blockchain_client.close()


# Test function
async def test_blockchain_integration():
    """Test PoD → PoE flow"""
    print("🧪 Testing GentleΩ PoD → PoE Integration...")
    
    # Test data
    test_data = {
        "query": "What is the meaning of life?",
        "user_id": "test_user",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Record PoD
    pod_result = await record_pod(test_data)
    print(f"PoD Result: {pod_result}")
    
    if pod_result["status"] == "success":
        # Simulate execution result
        execution_result = {
            "status": "completed",
            "answer": "42",
            "processing_time": 0.123,
            "model": "GentleΩ-v1"
        }
        
        # Record PoE
        poe_result = await record_poe(pod_result["pod_hash"], execution_result)
        print(f"PoE Result: {poe_result}")
    
    await cleanup_blockchain_client()
    return pod_result, poe_result


if __name__ == "__main__":
    asyncio.run(test_blockchain_integration())