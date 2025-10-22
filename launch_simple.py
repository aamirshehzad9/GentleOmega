"""
GentleΩ HeadQuarter Simple Launcher
Launches FastAPI and Streamlit with minimal logging to avoid Unicode issues
"""

import subprocess
import time
import sys
from pathlib import Path

def main():
    print("🧠 GentleΩ HeadQuarter Simple Launcher")
    print("=" * 50)
    
    # Use virtual environment python
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    python_cmd = str(venv_python) if venv_python.exists() else "python"
    
    print(f"Using Python: {python_cmd}")
    
    # Start FastAPI in background
    print("🚀 Starting FastAPI server...")
    fastapi_process = subprocess.Popen([
        python_cmd, "-m", "uvicorn", "app.app:app", 
        "--host", "127.0.0.1", 
        "--port", "8000",
        "--log-level", "warning"  # Reduce logging to avoid Unicode issues
    ], cwd="app")
    
    # Wait for FastAPI to start
    print("⏳ Waiting for FastAPI startup...")
    time.sleep(5)
    
    # Start Streamlit
    print("🚀 Starting Streamlit dashboard...")
    streamlit_process = subprocess.Popen([
        python_cmd, "-m", "streamlit", "run", "headquarters.py",
        "--server.port", "8501",
        "--server.address", "127.0.0.1",
        "--logger.level", "error"  # Reduce logging
    ], cwd="app")
    
    print("\n" + "=" * 50)
    print("🎯 GentleΩ HeadQuarter Access Points:")
    print("📊 Dashboard:    http://127.0.0.1:8501")
    print("🔗 API Health:   http://127.0.0.1:8000/health")
    print("📚 API Docs:     http://127.0.0.1:8000/docs")
    print("=" * 50)
    
    print("\n✅ Both services started successfully!")
    print("Press Ctrl+C to shutdown...")
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        
        # Terminate processes
        if fastapi_process.poll() is None:
            fastapi_process.terminate()
        if streamlit_process.poll() is None:
            streamlit_process.terminate()
        
        print("✅ Shutdown complete")

if __name__ == "__main__":
    main()