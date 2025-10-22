"""
GentleΩ Phase 5 Demonstration Script
Test all components of the HeadQuarter visual dashboard system
"""

import time
import subprocess
import requests
import os
from pathlib import Path

def print_section(title):
    print("\n" + "="*60)
    print(f"🧠 {title}")
    print("="*60)

def test_api_endpoints():
    """Test the new FastAPI endpoints"""
    print_section("Testing FastAPI Enhanced Endpoints")
    
    base_url = "http://127.0.0.1:8000"
    endpoints_to_test = [
        "/health",
        "/chain/status", 
        "/chain/metrics",
        "/logs/recent?lines=5",
        "/chain/ledger?limit=5"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            print(f"\n🔍 Testing {endpoint}")
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS: {endpoint}")
                # Show some sample data
                if endpoint == "/health":
                    print(f"   Status: {data.get('status', 'unknown')}")
                elif endpoint == "/chain/metrics":
                    print(f"   Ledger Total: {data.get('ledger_total', 0)}")
                    print(f"   RPC Status: {'Online' if data.get('rpc_connectivity') else 'Offline'}")
                elif endpoint == "/logs/recent?lines=5":
                    logs = data.get('logs', [])
                    print(f"   Recent logs: {len(logs)} entries")
                else:
                    print(f"   Response keys: {list(data.keys())}")
            else:
                print(f"❌ FAILED: {endpoint} - Status {response.status_code}")
        except Exception as e:
            print(f"❌ ERROR: {endpoint} - {str(e)}")

def show_component_status():
    """Show status of all Phase 5 components"""
    print_section("GentleΩ Phase 5 Component Status")
    
    components = [
        ("FastAPI Backend", "d:/GentleOmega/app/app.py"),
        ("Streamlit Dashboard", "d:/GentleOmega/app/headquarters.py"),
        ("MSSQL Sync Module", "d:/GentleOmega/app/mssql_sync.py"),
        ("HeadQuarter Launcher", "d:/GentleOmega/start_headquarters.py"),
        ("Enhanced Requirements", "d:/GentleOmega/app/requirements.txt"),
        ("Environment Config", "d:/GentleOmega/env/.env")
    ]
    
    for name, path in components:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ {name:<25} | {path} ({size:,} bytes)")
        else:
            print(f"❌ {name:<25} | Missing: {path}")

def show_api_documentation():
    """Display available API endpoints"""
    print_section("Available API Endpoints")
    
    endpoints = [
        ("GET /health", "System health check"),
        ("GET /chain/status", "Basic blockchain status"),
        ("GET /chain/metrics", "Detailed blockchain metrics for dashboard"),
        ("GET /chain/ledger", "Recent blockchain ledger entries with pagination"),
        ("GET /logs/recent", "Recent log entries from chain sync log"),
        ("POST /chain/cycle", "Manually trigger blockchain synchronization cycle"),
        ("GET /docs", "Interactive FastAPI documentation")
    ]
    
    for endpoint, description in endpoints:
        print(f"📡 {endpoint:<20} | {description}")

def show_streamlit_features():
    """Display Streamlit dashboard features"""
    print_section("GentleΩ HeadQuarter Dashboard Features")
    
    features = [
        "🎛️ Control Panel with auto-refresh toggle",
        "🔄 Manual refresh and chain cycle triggers", 
        "💚 Real-time system health monitoring",
        "📊 Chain status overview with metrics cards",
        "📈 PoE status distribution pie chart",
        "📋 Live log viewer with color-coded messages",
        "📜 Interactive blockchain ledger table",
        "📊 Performance timeline graphs",
        "🔗 Direct links to API documentation"
    ]
    
    for feature in features:
        print(f"  {feature}")

def show_mssql_sync_capabilities():
    """Display MSSQL synchronization features"""
    print_section("PostgreSQL → MSSQL Sync Features")
    
    capabilities = [
        "🔄 Automatic schema initialization in MSSQL",
        "📦 Batch synchronization with configurable size",
        "⏰ Continuous sync daemon (15-minute intervals)",
        "📊 Sync status tracking and error monitoring", 
        "🔍 Table-specific sync with incremental updates",
        "🛡️ Windows Authentication support",
        "🗂️ Support for blockchain_ledger, pods_poe, memories tables",
        "📈 Sync metrics and performance monitoring"
    ]
    
    for capability in capabilities:
        print(f"  {capability}")

def show_usage_instructions():
    """Show how to use the HeadQuarter system"""
    print_section("GentleΩ HeadQuarter Usage Instructions")
    
    print("""
🚀 STARTING THE SYSTEM:
   1. Run: python start_headquarters.py
   2. Choose whether to start MSSQL sync daemon
   3. Access dashboard at: http://127.0.0.1:8501
   4. Access API docs at: http://127.0.0.1:8000/docs

🎯 DASHBOARD NAVIGATION:
   • Left sidebar: Control panel and system health
   • Main area: Chain status, metrics, and PoE charts  
   • Right panel: Recent logs and system information
   • Bottom section: Blockchain ledger table

🔧 MSSQL SYNC OPERATIONS:
   • python app/mssql_sync.py test    - Test connections
   • python app/mssql_sync.py init    - Initialize MSSQL schema
   • python app/mssql_sync.py sync    - One-time sync
   • python app/mssql_sync.py daemon  - Continuous sync

⚙️ CONFIGURATION:
   • Edit env/.env for database and API settings
   • Adjust sync intervals in MSSQL_* variables
   • Configure dashboard auto-refresh in sidebar
    """)

def main():
    print("🧠 GentleΩ Phase 5: HeadQuarter Visual Dashboard System")
    print("=" * 60)
    print("Memory-Augmented AI Orchestrator with Visual Control Center")
    
    show_component_status()
    show_api_documentation()
    show_streamlit_features()
    show_mssql_sync_capabilities()
    show_usage_instructions()
    
    print_section("Testing Live API Endpoints")
    print("Note: This requires the FastAPI server to be running")
    print("Start with: cd d:/GentleOmega && python -m uvicorn app.app:app --host 127.0.0.1 --port 8000")
    
    # Test if server is running
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=2)
        if response.status_code == 200:
            test_api_endpoints()
        else:
            print("\n⚠️ FastAPI server not responding. Start it first to test endpoints.")
    except:
        print("\n⚠️ FastAPI server not running. Start it first to test endpoints.")
    
    print_section("GentleΩ Phase 5 Demonstration Complete")
    print("""
✅ ACHIEVEMENTS:
   • Enhanced FastAPI with dashboard-ready endpoints
   • Built comprehensive Streamlit visual dashboard
   • Implemented PostgreSQL → MSSQL synchronization  
   • Created unified HeadQuarter startup system
   • Added real-time monitoring and control capabilities

🎯 NEXT STEPS:
   • Run: python start_headquarters.py
   • Access: http://127.0.0.1:8501 (Dashboard)
   • Monitor: Real-time blockchain and PoE operations
   • Sync: Automatic PostgreSQL → MSSQL backup replication
    """)

if __name__ == "__main__":
    main()