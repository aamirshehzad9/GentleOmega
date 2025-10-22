#!/usr/bin/env python3
"""
GentleΩ HQ Full Production Launcher
Starts both FastAPI backend and Streamlit dashboard with live database connectivity
"""

import subprocess
import os
import time
import sys
import signal
from pathlib import Path

def setup_environment():
    """Configure environment variables for production"""
    env = os.environ.copy()
    
    # Database configuration
    env["PG_HOST"] = "127.0.0.1"
    env["PG_PORT"] = "5432"
    env["PG_DB"] = "metacity"
    env["PG_USER"] = "postgres"
    env["PG_PASSWORD"] = "postgres"  # Update this with your actual password
    env["DATABASE_URL"] = f"postgresql://{env['PG_USER']}:{env['PG_PASSWORD']}@{env['PG_HOST']}:{env['PG_PORT']}/{env['PG_DB']}"
    
    # API configuration
    env["SERVICE_PORT"] = "8000"
    
    # Blockchain configuration (simulation mode by default)
    env["CHAIN_RPC"] = "https://your-chain-endpoint"  # Will use simulation mode
    
    # Embeddings configuration
    env["EMBEDDINGS_BACKEND"] = "local"
    env["EMBEDDINGS_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
    
    return env

def check_dependencies():
    """Check if required services and dependencies are available"""
    print("🔍 Checking dependencies...")
    
    # Check if PostgreSQL is accessible
    try:
        import psycopg2
        conn_str = "postgresql://postgres:postgres@127.0.0.1:5432/metacity"
        conn = psycopg2.connect(conn_str)
        conn.close()
        print("✅ PostgreSQL connection: OK")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("   Make sure PostgreSQL is running and credentials are correct")
        return False
    
    # Check if ports are available
    import socket
    for port, service in [(8000, "FastAPI"), (8501, "Streamlit")]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            print(f"⚠️  Port {port} ({service}) is already in use")
            return False
        else:
            print(f"✅ Port {port} ({service}): Available")
    
    return True

def main():
    print("🚀 GentleΩ HQ Full Production Launcher")
    print("=" * 50)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n❌ Dependency check failed. Please resolve issues before continuing.")
        return 1
    
    # Setup environment
    env = setup_environment()
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Start FastAPI Backend
    print("\n🚀 Starting FastAPI Backend...")
    fastapi_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.app:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        env=env,
        cwd=project_root
    )
    
    # Wait for FastAPI to start
    print("⏳ Waiting for FastAPI to initialize...")
    time.sleep(8)
    
    # Verify FastAPI is running
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ FastAPI Backend: Ready")
        else:
            print(f"⚠️  FastAPI Backend: Started but health check failed ({response.status_code})")
    except Exception as e:
        print(f"⚠️  FastAPI Backend: Health check failed - {e}")
    
    # Start Streamlit Dashboard
    print("\n🚀 Starting Streamlit Dashboard...")
    streamlit_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/headquarters.py", 
         "--server.port", "8501", "--server.headless", "true", "--server.address", "127.0.0.1"],
        env=env,
        cwd=project_root
    )
    
    # Wait for Streamlit to start
    print("⏳ Waiting for Streamlit to initialize...")
    time.sleep(5)
    
    print("\n" + "=" * 50)
    print("🎉 GentleΩ HQ is now running in PRODUCTION MODE!")
    print("=" * 50)
    print("🌐 FastAPI Backend:     http://127.0.0.1:8000")
    print("📊 Streamlit Dashboard: http://127.0.0.1:8501")
    print("📚 API Documentation:   http://127.0.0.1:8000/docs")
    print("=" * 50)
    print("🔄 Both services are running with LIVE database connectivity")
    print("🛑 Press Ctrl+C to stop both services")
    print("=" * 50)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("\n🛑 Stopping services...")
        try:
            fastapi_proc.terminate()
            streamlit_proc.terminate()
            
            # Wait for processes to terminate gracefully
            fastapi_proc.wait(timeout=5)
            streamlit_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("🔥 Force killing processes...")
            fastapi_proc.kill()
            streamlit_proc.kill()
        
        print("✅ All services stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep the launcher running and monitor processes
    try:
        while True:
            # Check if processes are still running
            if fastapi_proc.poll() is not None:
                print("❌ FastAPI process died unexpectedly!")
                break
            
            if streamlit_proc.poll() is not None:
                print("❌ Streamlit process died unexpectedly!")
                break
            
            time.sleep(10)
    
    except KeyboardInterrupt:
        signal_handler(None, None)
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)