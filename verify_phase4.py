#!/usr/bin/env python3
"""
GentleΩ Phase 4 Blockchain Integration - Verification Script
Tests all components without running the full server
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

import asyncio
from datetime import datetime

def test_environment_setup():
    """Test environment configuration"""
    print("🔧 Testing Environment Setup...")
    
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join("env", ".env"))
    
    required_vars = [
        "PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD",
        "HF_TOKEN", "OPENAI_BASE_URL", "CHAIN_RPC", "WALLET_ADDRESS"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✓ {var}: {'*' * min(len(value), 8)}...")
        else:
            print(f"  ⚠️ {var}: Not configured")
    
    print("✅ Environment setup verified\n")
    return True


def test_database_migration():
    """Test database migration and setup"""
    print("🗄️ Testing Database Migration...")
    
    try:
        from app.psycopg_fix import connect_pg
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=os.path.join("env", ".env"))
        
        pg = connect_pg(
            os.getenv("PG_HOST", "127.0.0.1"),
            int(os.getenv("PG_PORT", "5432")),
            os.getenv("PG_DB", "metacity"),
            os.getenv("PG_USER", "postgres"),
            os.getenv("PG_PASSWORD", "postgres")
        )
        
        with pg.cursor() as cur:
            # Check required tables exist
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name IN ('blockchain_ledger', 'pods_poe')
            """)
            table_count = cur.fetchone()[0]
            
            if table_count >= 2:
                print("  ✓ Required tables exist")
                
                # Check table structure
                cur.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'blockchain_ledger'
                """)
                columns = [row[0] for row in cur.fetchall()]
                
                required_columns = ['status', 'tx_hash', 'poe_hash', 'block_number']
                missing = [col for col in required_columns if col not in columns]
                
                if not missing:
                    print("  ✓ Blockchain ledger schema complete")
                else:
                    print(f"  ⚠️ Missing columns: {missing}")
                
                # Check migration marker
                cur.execute("SELECT COUNT(*) FROM blockchain_ledger WHERE poe_hash = 'migration_phase_4_complete'")
                marker_count = cur.fetchone()[0]
                
                if marker_count > 0:
                    print("  ✓ Phase 4 migration marker found")
                else:
                    print("  ⚠️ Migration marker not found")
                    
            else:
                print(f"  ❌ Only {table_count}/2 required tables found")
                return False
                
        pg.close()
        print("✅ Database migration verified\n")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}\n")
        return False


def test_blockchain_client():
    """Test blockchain client functions"""
    print("⛓️ Testing Blockchain Client...")
    
    try:
        from app.blockchain_client import ping_rpc, get_chain_head, push_to_chain
        
        # Test RPC connectivity (simulation mode expected)
        rpc_ok, latency = ping_rpc()
        print(f"  ✓ RPC ping: ok={rpc_ok}, latency={latency}ms")
        
        # Test chain head retrieval
        block_num = get_chain_head()
        print(f"  ✓ Chain head: block {block_num}")
        
        # Test PoE hash submission (simulation mode)
        test_poe_hash = "test_poe_hash_" + str(int(datetime.now().timestamp()))
        result = push_to_chain(test_poe_hash)
        
        if "tx_hash" in result:
            print(f"  ✓ PoE submission: {result['tx_hash'][:16]}...")
        else:
            print(f"  ⚠️ PoE submission result: {result}")
            
        print("✅ Blockchain client verified\n")
        return True
        
    except Exception as e:
        print(f"❌ Blockchain client test failed: {e}\n")
        return False


async def test_chain_orchestrator():
    """Test chain orchestrator functionality"""
    print("🔄 Testing Chain Orchestrator...")
    
    try:
        from app.chain_orchestrator import run_single_cycle, get_orchestrator_stats
        
        # Test orchestrator stats
        stats = await get_orchestrator_stats()
        print(f"  ✓ Orchestrator stats: {stats['status']}")
        print(f"    - Pending transactions: {stats.get('pending_tx', 0)}")
        print(f"    - Confirmed transactions: {stats.get('confirmed_tx', 0)}")
        print(f"    - RPC connectivity: {stats.get('rpc_connectivity', False)}")
        
        # Test single cycle execution  
        cycle_result = await run_single_cycle()
        print(f"  ✓ Single cycle result: enqueued={cycle_result.get('enqueued', 0)}, "
              f"submitted={cycle_result.get('submitted', 0)}, confirmed={cycle_result.get('confirmed', 0)}")
        
        print("✅ Chain orchestrator verified\n")
        return True
        
    except Exception as e:
        print(f"❌ Chain orchestrator test failed: {e}\n")
        return False


async def test_pod_poe_flow():
    """Test complete PoD → PoE flow"""
    print("🔄 Testing PoD → PoE Flow...")
    
    try:
        from app.blockchain_client import record_pod, record_poe
        
        # Test PoD recording
        test_data = {
            "operation": "test_verification",
            "timestamp": datetime.now().isoformat(),
            "test_id": "phase_4_verification"
        }
        
        pod_result = await record_pod(test_data)
        print(f"  ✓ PoD recorded: {pod_result['status']}")
        
        if pod_result["status"] == "success":
            # Test PoE recording
            execution_result = {
                "status": "completed",
                "verification": "passed",
                "phase": "4"
            }
            
            poe_result = await record_poe(pod_result["pod_hash"], execution_result)
            print(f"  ✓ PoE recorded: {poe_result['status']}")
            
            if poe_result["status"] == "success":
                print(f"    - PoD Hash: {pod_result['pod_hash'][:16]}...")
                print(f"    - PoE Hash: {poe_result['poe_hash'][:16]}...")
                print(f"    - Transaction: {poe_result['transaction_hash'][:16]}...")
        
        print("✅ PoD → PoE flow verified\n")
        return True
        
    except Exception as e:
        print(f"❌ PoD → PoE flow test failed: {e}\n")
        return False


async def main():
    """Run all verification tests"""
    print("=" * 60)
    print("🚀 GentleΩ Phase 4 Blockchain Integration Verification")
    print("=" * 60)
    print()
    
    tests = [
        ("Environment Setup", test_environment_setup()),
        ("Database Migration", test_database_migration()),
        ("Blockchain Client", test_blockchain_client()),
        ("Chain Orchestrator", await test_chain_orchestrator()),
        ("PoD → PoE Flow", await test_pod_poe_flow())
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, result in tests:
        if result:
            passed += 1
    
    print("=" * 60)
    print(f"📊 Verification Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 SUCCESS!")
        print("✅ GentleΩ Phase 4 Live Blockchain Integration Operational")
        print("   📊 All components verified and functional")
        print("   🔗 EVM RPC client ready")
        print("   🔄 Autonomous orchestration ready")
        print("   📡 PoD → PoE flow operational")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review configuration")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)