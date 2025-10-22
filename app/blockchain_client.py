"""
GentleΩ Blockchain Client - PoD → PoE Integration
Handles Proof of Data (PoD) and Proof of Execution (PoE) recording
"""

import os
import json
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

CHAIN_RPC = os.getenv("CHAIN_RPC", "https://your-chain-endpoint")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "your_private_key")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "your_wallet_address")


class BlockchainClient:
    """Async blockchain client for PoD/PoE transactions"""
    
    def __init__(self):
        self.rpc_url = CHAIN_RPC
        self.private_key = WALLET_PRIVATE_KEY
        self.wallet_address = WALLET_ADDRESS
        self.session: Optional[aiohttp.ClientSession] = None
    
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
    
    async def record_pod(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record Proof of Data (PoD) transaction
        
        Args:
            data: Data to be recorded on blockchain
            
        Returns:
            Transaction result with hash and timestamp
        """
        try:
            pod_hash = self._generate_pod_hash(data)
            timestamp = datetime.now(timezone.utc).isoformat()
            
            transaction_payload = {
                "type": "POD",
                "data_hash": pod_hash,
                "timestamp": timestamp,
                "wallet_address": self.wallet_address,
                "data_summary": {
                    "keys": list(data.keys()),
                    "size": len(json.dumps(data))
                }
            }
            
            # Simulate blockchain transaction
            if self.rpc_url == "https://your-chain-endpoint":
                print(f"🔗 [SIMULATION] PoD Transaction: {pod_hash[:16]}...")
                return {
                    "status": "success",
                    "transaction_hash": f"pod_{pod_hash[:32]}",
                    "pod_hash": pod_hash,
                    "timestamp": timestamp,
                    "simulation": True
                }
            
            # Real blockchain transaction
            session = await self._get_session()
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
        Record Proof of Execution (PoE) transaction
        
        Args:
            pod_hash: Hash from the original PoD transaction
            execution_result: Result of data processing/execution
            
        Returns:
            Transaction result with PoE hash and verification
        """
        try:
            poe_hash = self._generate_poe_hash(pod_hash, execution_result)
            timestamp = datetime.now(timezone.utc).isoformat()
            
            verification_payload = {
                "type": "POE",
                "pod_hash": pod_hash,
                "poe_hash": poe_hash,
                "timestamp": timestamp,
                "wallet_address": self.wallet_address,
                "execution_summary": {
                    "status": execution_result.get("status", "completed"),
                    "result_size": len(json.dumps(execution_result)),
                    "processing_time": execution_result.get("processing_time")
                }
            }
            
            # Simulate blockchain transaction
            if self.rpc_url == "https://your-chain-endpoint":
                print(f"✅ [SIMULATION] PoE Verification: {poe_hash[:16]}...")
                return {
                    "status": "success",
                    "transaction_hash": f"poe_{poe_hash[:32]}",
                    "pod_hash": pod_hash,
                    "poe_hash": poe_hash,
                    "timestamp": timestamp,
                    "verification": "complete",
                    "simulation": True
                }
            
            # Real blockchain transaction
            session = await self._get_session()
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