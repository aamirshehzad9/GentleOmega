"""
GentleΩ Phase 4 Integration Test Script
Tests the complete EVM blockchain integration
"""

import asyncio
import sys
import os
import time
from typing import Dict, Any
import httpx
from dotenv import load_dotenv

# Add app directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Load environment
load_dotenv(dotenv_path=os.path.join("env", ".env"))

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_CONTENT = "Phase 4 blockchain integration test"
TEST_USER = "test_user_phase4"


async def test_api_endpoint(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Test an API endpoint and return result"""
    try:
        response = await client.request(method, url, **kwargs)
        result = {
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }
        return result
    except Exception as e:
        return {
            "status_code": 0,
            "success": False,
            "error": str(e)
        }


async def run_integration_tests():
    """Run comprehensive Phase 4 integration tests"""
    print("🧪 GentleΩ Phase 4 Blockchain Integration Tests")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        tests_passed = 0
        tests_total = 0
        
        # Test 1: Health check with blockchain components
        print("\n1️⃣ Testing health endpoint with blockchain metrics...")
        tests_total += 1
        health_result = await test_api_endpoint(client, "GET", f"{BASE_URL}/health")
        
        if health_result["success"]:
            health_data = health_result["data"]
            print(f"   ✅ Health: {health_data.get('status', 'unknown')}")
            print(f"   🔗 Blockchain: {health_data.get('blockchain', 'unknown')}")
            
            components = health_data.get('components', {})
            print(f"   📡 RPC Connectivity: {components.get('rpc_connectivity', False)}")
            print(f"   ⏱️  Chain Latency: {components.get('chain_latency_ms', -1)}ms")
            print(f"   🧮 Last Block: {components.get('last_block', -1)}")
            tests_passed += 1
        else:
            print(f"   ❌ Health check failed: {health_result}")
        
        # Test 2: Chain status endpoint
        print("\n2️⃣ Testing /chain/status endpoint...")
        tests_total += 1
        chain_result = await test_api_endpoint(client, "GET", f"{BASE_URL}/chain/status")
        
        if chain_result["success"]:
            chain_data = chain_result["data"]
            print(f"   ✅ Chain Status: {chain_data.get('status', 'unknown')}")
            print(f"   📊 Pending TX: {chain_data.get('pending_tx', 0)}")
            print(f"   ✔️ Verified TX: {chain_data.get('verified', 0)}")
            print(f"   ❌ Failed TX: {chain_data.get('failed_tx', 0)}")
            print(f"   ⏳ Queued TX: {chain_data.get('queued_tx', 0)}")
            print(f"   📡 RPC OK: {chain_data.get('rpc_ok', False)}")
            tests_passed += 1
        else:
            print(f"   ❌ Chain status failed: {chain_result}")
        
        # Test 3: Create item with PoD tracking
        print("\n3️⃣ Testing item creation with PoD tracking...")
        tests_total += 1
        create_result = await test_api_endpoint(
            client, "POST", f"{BASE_URL}/items",
            params={"content": TEST_CONTENT, "user_id": TEST_USER}
        )
        
        if create_result["success"]:
            create_data = create_result["data"]
            print(f"   ✅ Created item: {create_data.get('item_id', 'unknown')}")
            print(f"   🔐 Status: {create_data.get('status', 'unknown')}")
            tests_passed += 1
            item_id = create_data.get('item_id')
        else:
            print(f"   ❌ Item creation failed: {create_result}")
            item_id = None
        
        # Test 4: Retrieve item with PoE tracking
        if item_id:
            print("\n4️⃣ Testing item retrieval with PoE tracking...")
            tests_total += 1
            get_result = await test_api_endpoint(client, "GET", f"{BASE_URL}/items/{item_id}")
            
            if get_result["success"]:
                get_data = get_result["data"]
                print(f"   ✅ Retrieved item: {item_id}")
                blockchain_info = get_data.get('blockchain', {})
                print(f"   🔐 PoD Hash: {blockchain_info.get('pod_hash', 'N/A')[:16]}...")
                print(f"   🔗 TX Hash: {blockchain_info.get('transaction_hash', 'N/A')[:16]}...")
                tests_passed += 1
            else:
                print(f"   ❌ Item retrieval failed: {get_result}")
        
        # Test 5: Embedding with PoD/PoE flow
        print("\n5️⃣ Testing embedding generation with PoD/PoE flow...")
        tests_total += 1
        embed_result = await test_api_endpoint(
            client, "POST", f"{BASE_URL}/embed",
            params={"text": "Phase 4 test embedding"}
        )
        
        if embed_result["success"]:
            embed_data = embed_result["data"]
            print(f"   ✅ Generated embedding: {embed_data.get('dim', 0)} dimensions")
            blockchain_info = embed_data.get('blockchain', {})
            print(f"   🔐 PoD Hash: {blockchain_info.get('pod_hash', 'N/A')[:16]}...")
            print(f"   🔗 TX Hash: {blockchain_info.get('transaction_hash', 'N/A')[:16]}...")
            tests_passed += 1
        else:
            print(f"   ❌ Embedding generation failed: {embed_result}")
        
        # Test 6: Manual chain cycle trigger
        print("\n6️⃣ Testing manual chain orchestration cycle...")
        tests_total += 1
        cycle_result = await test_api_endpoint(client, "POST", f"{BASE_URL}/chain/cycle")
        
        if cycle_result["success"]:
            cycle_data = cycle_result["data"]
            print(f"   ✅ Chain cycle: {cycle_data.get('status', 'unknown')}")
            metrics = cycle_data.get('metrics', {})
            print(f"   📊 Enqueued: {metrics.get('enqueued', 0)}")
            print(f"   📤 Submitted: {metrics.get('submitted', 0)}")  
            print(f"   ✔️ Confirmed: {metrics.get('confirmed', 0)}")
            tests_passed += 1
        else:
            print(f"   ❌ Chain cycle failed: {cycle_result}")
        
        # Wait a moment and check chain status again
        print("\n7️⃣ Re-checking chain status after operations...")
        tests_total += 1
        await asyncio.sleep(2)  # Give time for background processing
        
        final_chain_result = await test_api_endpoint(client, "GET", f"{BASE_URL}/chain/status")
        if final_chain_result["success"]:
            final_data = final_chain_result["data"]
            print(f"   ✅ Final chain status: {final_data.get('status', 'unknown')}")
            print(f"   📊 Final pending: {final_data.get('pending_tx', 0)}")
            print(f"   ✔️ Final verified: {final_data.get('verified', 0)}")
            tests_passed += 1
        else:
            print(f"   ❌ Final chain check failed: {final_chain_result}")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"🧪 Test Results: {tests_passed}/{tests_total} tests passed")
    
    if tests_passed == tests_total:
        print("🎉 ALL TESTS PASSED!")
        print("✅ GentleΩ Phase 4 Live Blockchain Integration Operational")
        return True
    else:
        print(f"⚠️  {tests_total - tests_passed} tests failed")
        print("❌ Phase 4 integration has issues")
        return False


async def database_setup_check():
    """Check if database migration is needed"""
    print("🔍 Checking database setup...")
    
    try:
        from chain_orchestrator import verify_setup
        if verify_setup():
            print("✅ Database setup verified")
            return True
        else:
            print("❌ Database setup incomplete")
            print("💡 Run: psql <your-db> -f db/migration_2025_10_22_blockchain_ledger.sql")
            return False
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False


def main():
    """Main test runner"""
    print("🚀 GentleΩ Phase 4 Blockchain Integration Test Suite")
    print(f"📅 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check if server is running
    try:
        import httpx
        response = httpx.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Server not responding at {BASE_URL}")
            print("💡 Start server with: uvicorn app:app --host 127.0.0.1 --port 8000 --reload")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"   Error: {e}")
        print("💡 Start server with: uvicorn app:app --host 127.0.0.1 --port 8000 --reload")
        return False
    
    # Run database checks
    if not asyncio.run(database_setup_check()):
        return False
    
    # Run integration tests
    success = asyncio.run(run_integration_tests())
    
    if success:
        print("\n🎊 Phase 4 integration test completed successfully!")
    else:
        print("\n⚠️  Phase 4 integration test found issues!")
    
    return success


if __name__ == "__main__":
    main()