#!/usr/bin/env python3
"""
Simple GentleΩ System Launcher
Starts both services in a more stable way
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def main():
    print("🚀 Starting GentleΩ Production System...")
    
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Setup environment
    env = os.environ.copy()
    env["PG_HOST"] = "127.0.0.1"
    env["PG_PORT"] = "5432"
    env["PG_DB"] = "metacity"
    env["PG_USER"] = "postgres"
    env["PG_PASSWORD"] = "postgres"
    env["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5432/metacity"
    env["EMBEDDINGS_BACKEND"] = "local"
    env["CHAIN_RPC"] = "https://your-chain-endpoint"  # Simulation mode
    
    print("\n🎯 CHOICE: Which service would you like to start?")
    print("1. FastAPI Backend only (http://127.0.0.1:8000)")
    print("2. Streamlit Dashboard only (http://127.0.0.1:8501)")  
    print("3. Both services")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1" or choice == "3":
        print("\n🚀 Starting FastAPI Backend...")
        fastapi_cmd = [
            sys.executable, "-m", "uvicorn", "app.app:app", 
            "--host", "127.0.0.1", "--port", "8000", "--reload"
        ]
        
        if choice == "1":
            # Run in foreground for single service
            subprocess.run(fastapi_cmd, env=env)
        else:
            # Start in background for dual service
            subprocess.Popen(fastapi_cmd, env=env)
            print("⏳ Waiting for backend to initialize...")
            time.sleep(10)
    
    if choice == "2" or choice == "3":
        print("\n🚀 Starting Streamlit Dashboard...")
        streamlit_cmd = [
            sys.executable, "-m", "streamlit", "run", "app/headquarters.py",
            "--server.port", "8501", "--server.headless", "true"
        ]
        
        # Streamlit runs in foreground
        subprocess.run(streamlit_cmd, env=env)
    
    if choice == "3":
        print("\n🎉 Both services running!")
        print("🌐 Backend: http://127.0.0.1:8000")
        print("📊 Dashboard: http://127.0.0.1:8501")
        print("\nPress Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")

if __name__ == "__main__":
    main()