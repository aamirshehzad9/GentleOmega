"""
GentleΩ HeadQuarter Simple Demo Launcher
Pure Streamlit demo without pandas/dataframes to avoid pyarrow dependency
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

def create_mock_logs():
    """Create mock log files for demo"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create mock chain sync log
    chain_log = logs_dir / "chain_sync.log"
    with open(chain_log, "w", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - INFO - GentleΩ Chain Orchestrator started\n")
        f.write(f"{datetime.now().isoformat()} - INFO - Blockchain sync cycle #1 completed\n")
        f.write(f"{datetime.now().isoformat()} - INFO - 5 PoE transactions confirmed\n")
        f.write(f"{datetime.now().isoformat()} - INFO - RPC latency: 120ms\n")
        f.write(f"{datetime.now().isoformat()} - INFO - Next sync cycle in 10 minutes\n")
    
    print(f"✅ Created mock logs at: {chain_log}")

def main():
    print("🧠 GentleΩ HeadQuarter Simple Demo")
    print("=" * 50)
    
    # Create mock data
    create_mock_logs()
    
    # Use virtual environment python
    venv_python = Path(".venv") / "Scripts" / "python.exe"
    python_cmd = str(venv_python) if venv_python.exists() else "python"
    
    print(f"Using Python: {python_cmd}")
    
    # Start Streamlit with our simple demo
    demo_file = Path("app") / "demo_simple.py"
    
    print("🚀 Starting Streamlit simple demo...")
    streamlit_process = subprocess.Popen([
        python_cmd, "-m", "streamlit", "run", str(demo_file),
        "--server.port", "8501",
        "--server.address", "127.0.0.1"
    ])
    
    print("\n" + "=" * 50)
    print("🎯 GentleΩ HeadQuarter Simple Demo:")
    print("📊 Dashboard:    http://127.0.0.1:8501")
    print("=" * 50)
    
    print("\n✅ Simple demo started!")
    print("🎯 Open http://127.0.0.1:8501 in your browser")
    print("Press Ctrl+C to shutdown...")
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down demo...")
        
        # Terminate process
        if streamlit_process.poll() is None:
            streamlit_process.terminate()
        
        print("✅ Demo shutdown complete")

if __name__ == "__main__":
    main()