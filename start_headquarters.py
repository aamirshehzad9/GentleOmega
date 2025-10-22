"""
GentleΩ Phase 5 Startup Script
Launches FastAPI backend and Streamlit dashboard simultaneously
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

def run_command(cmd, name, cwd=None):
    """Run a command and return the process"""
    try:
        print(f"🚀 Starting {name}...")
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
            shell=True
        )
        print(f"✅ {name} started (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ Failed to start {name}: {str(e)}")
        return None

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['streamlit', 'pandas', 'plotly', 'requests', 'pyodbc']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print("This is expected if running outside the virtual environment.")
        print("The script will attempt to use the virtual environment Python executable.")
        print("If issues persist, activate your venv and run: pip install -r app/requirements.txt")
        # Don't fail - let the script continue with venv python
        return True
    
    print("✅ All dependencies available")
    return True

def check_database_environment():
    """Check database environment configuration"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    PG_HOST = os.getenv("PG_HOST")
    PG_USER = os.getenv("PG_USER") 
    PG_DB = os.getenv("PG_DB")
    PG_PASSWORD = os.getenv("PG_PASSWORD")
    
    if DATABASE_URL or (PG_HOST and PG_USER and PG_DB and PG_PASSWORD):
        print("✅ Database environment configured - Production mode")
        return True
    else:
        print("⚠️  Database environment not configured - Will run in Demo mode")
        print("To enable production mode, set:")
        print("$env:PG_HOST=\"127.0.0.1\"")
        print("$env:PG_PORT=\"5432\"") 
        print("$env:PG_DB=\"metacity\"")
        print("$env:PG_USER=\"postgres\"")
        print("$env:PG_PASSWORD=\"<your_pg_password>\"")
        print("$env:DATABASE_URL=\"postgresql://postgres:<your_pg_password>@127.0.0.1:5432/metacity\"")
        return False

def main():
    print("🧠 GentleΩ HeadQuarter Startup")
    print("=" * 50)
    
    # Check database configuration
    db_configured = check_database_environment()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Change to app directory for relative imports
    app_dir = Path(__file__).parent / "app"
    
    processes = []
    
    try:
        # Use virtual environment Python
        venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
        python_cmd = str(venv_python) if venv_python.exists() else "python"
        
        # Start FastAPI backend
        fastapi_cmd = f"{python_cmd} -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload"
        fastapi_process = run_command(fastapi_cmd, "FastAPI Backend", cwd=app_dir)
        if fastapi_process:
            processes.append(("FastAPI", fastapi_process))
        
        # Wait a moment for FastAPI to start
        time.sleep(3)
        
        # Start Streamlit dashboard
        streamlit_cmd = f"{python_cmd} -m streamlit run headquarters.py --server.port 8501 --server.address 127.0.0.1"
        streamlit_process = run_command(streamlit_cmd, "Streamlit Dashboard", cwd=app_dir)
        if streamlit_process:
            processes.append(("Streamlit", streamlit_process))
        
        # Optionally start MSSQL sync daemon
        sync_choice = input("\n🔄 Start MSSQL sync daemon? (y/N): ").lower().strip()
        if sync_choice in ['y', 'yes']:
            sync_cmd = f"{python_cmd} mssql_sync.py daemon"
            sync_process = run_command(sync_cmd, "MSSQL Sync Daemon", cwd=app_dir)
            if sync_process:
                processes.append(("MSSQL Sync", sync_process))
        
        if not processes:
            print("❌ No processes started successfully")
            sys.exit(1)
        
        # Display access URLs
        print("\n" + "=" * 50)
        print("🎯 GentleΩ HeadQuarter Access Points:")
        print("📊 Dashboard:    http://127.0.0.1:8501")
        print("🔗 API Docs:     http://127.0.0.1:8000/docs")
        print("💾 API Health:   http://127.0.0.1:8000/health")
        print("🔍 Chain Status: http://127.0.0.1:8000/chain/status")
        print("=" * 50)
        
        print(f"\n✅ {len(processes)} services running")
        print("Press Ctrl+C to shutdown all services...")
        
        # Wait for interruption
        while True:
            time.sleep(1)
            
            # Check if any process died
            for name, process in processes:
                if process.poll() is not None:
                    print(f"⚠️ {name} process ended unexpectedly")
    
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested...")
        
    except Exception as e:
        print(f"❌ Startup error: {str(e)}")
    
    finally:
        # Cleanup processes
        print("🔄 Stopping services...")
        for name, process in processes:
            try:
                if process.poll() is None:  # Process still running
                    print(f"Stopping {name}...")
                    if os.name == 'nt':  # Windows
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                     capture_output=True)
                    else:  # Unix-like
                        process.terminate()
                        process.wait(timeout=5)
            except Exception as e:
                print(f"Warning: Could not stop {name}: {str(e)}")
        
        print("✅ Shutdown complete")

if __name__ == "__main__":
    main()