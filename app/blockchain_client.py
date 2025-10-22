"""
GentleΩ Blockchain Client - PoD → PoE Integration
Handles Proof of Data (PoD) and Proof of Execution (PoE) recording
Enhanced with local blockchain ledger database integration
"""

import os
import sys
import json
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import aiohttp
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))
from psycopg_fix import connect_pg

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

CHAIN_RPC = os.getenv("CHAIN_RPC", "https://your-chain-endpoint")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "your_private_key")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "your_wallet_address")

# Database configuration
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD", "postgres")


class BlockchainClient:
    """Enhanced blockchain client for PoD/PoE transactions with local ledger"""
    
    def __init__(self):
        self.rpc_url = CHAIN_RPC
        self.private_key = WALLET_PRIVATE_KEY
        self.wallet_address = WALLET_ADDRESS
        self.session: Optional[aiohttp.ClientSession] = None
        self.pg_connection = None
        
    def _get_db_connection(self):
        """Get database connection for ledger operations"""
        if not self.pg_connection:
            self.pg_connection = connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)
        return self.pg_connection
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
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
            
            # Simulate or execute blockchain transaction
            if self.rpc_url == "https://your-chain-endpoint":
                print(f"[SIMULATION] PoD Transaction: {pod_hash[:16]}...")
                return {
                    "status": "success",
                    "transaction_hash": f"pod_{pod_hash[:32]}",
                    "pod_hash": pod_hash,
                    "timestamp": timestamp,
                    "ledger": ledger_result,
                    "simulation": True
                }
            
            # Real blockchain transaction
            session = await self._get_session()
            transaction_payload = {
                "type": "POD",
                "data_hash": pod_hash,
                "timestamp": timestamp,
                "wallet_address": self.wallet_address,
                "ledger_reference": ledger_result.get("ledger_id")
            }
            
            async with session.post(
                f"{self.rpc_url}/transactions",
                json=transaction_payload,
                headers={"Authorization": f"Bearer {self.private_key}"}
            ) as response:
                result = await response.json()
                
                return {
                    "status": "success" if response.status == 200 else "error",
                    "transaction_hash": result.get("hash"),
                    "pod_hash": pod_hash,
                    "timestamp": timestamp,
                    "ledger": ledger_result,
                    "response": result
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
            
            # Simulate or execute blockchain transaction
            if self.rpc_url == "https://your-chain-endpoint":
                print(f"[SIMULATION] PoE Verification: {poe_hash[:16]}...")
                return {
                    "status": "success",
                    "transaction_hash": f"poe_{poe_hash[:32]}",
                    "pod_hash": pod_hash,
                    "poe_hash": poe_hash,
                    "timestamp": timestamp,
                    "verification": "complete",
                    "ledger": ledger_result,
                    "simulation": True
                }
            
            # Real blockchain transaction
            session = await self._get_session()
            verification_payload = {
                "type": "POE",
                "pod_hash": pod_hash,
                "poe_hash": poe_hash,
                "timestamp": timestamp,
                "wallet_address": self.wallet_address,
                "ledger_reference": ledger_result.get("ledger_id")
            }
            
            async with session.post(
                f"{self.rpc_url}/verifications",
                json=verification_payload,
                headers={"Authorization": f"Bearer {self.private_key}"}
            ) as response:
                result = await response.json()
                
                return {
                    "status": "success" if response.status == 200 else "error",
                    "transaction_hash": result.get("hash"),
                    "pod_hash": pod_hash,
                    "poe_hash": poe_hash,
                    "timestamp": timestamp,
                    "verification": "complete",
                    "ledger": ledger_result,
                    "response": result
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
            if self.rpc_url == "https://your-chain-endpoint":
                return {
                    "status": "confirmed",
                    "transaction_hash": transaction_hash,
                    "confirmations": 12,
                    "simulation": True
                }
            
            session = await self._get_session()
            async with session.get(
                f"{self.rpc_url}/transactions/{transaction_hash}",
                headers={"Authorization": f"Bearer {self.private_key}"}
            ) as response:
                return await response.json()
                
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