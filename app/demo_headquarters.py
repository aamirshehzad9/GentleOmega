
import streamlit as st
import json
from datetime import datetime

st.set_page_config(
    page_title="GentleΩ HeadQuarter - DEMO MODE",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🧠 GentleΩ HeadQuarter - DEMO MODE")
st.markdown("*Memory-Augmented AI Orchestrator with Blockchain Proofs*")
st.warning("⚠️ Demo Mode: Using mock data (Database not connected)")

# Sidebar Controls
with st.sidebar:
    st.header("🎛️ Control Panel")
    st.checkbox("Auto Refresh (10s)", value=True)
    if st.button("🔄 Refresh Now"):
        st.rerun()
    
    st.subheader("System Health")
    st.success("✅ Demo Mode Active")

# Main Dashboard Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🔗 Blockchain Status")
    
    # Create metrics cards
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
    with metric_col1:
        st.metric("Current Block", 1234567)
    with metric_col2:
        st.metric("Last Confirmed", 1234565)
    with metric_col3:
        st.metric("Ledger Entries", 89)
    with metric_col4:
        st.metric("RPC Latency", "120ms")
    
    st.success("🟢 Blockchain Synchronized (Demo)")

with col2:
    st.subheader("📋 Recent Logs")
    st.info("GentleΩ Chain Orchestrator started")
    st.info("Blockchain sync cycle #1 completed")
    st.info("5 PoE transactions confirmed") 
    st.info("RPC latency: 120ms")
    st.info("Next sync cycle in 10 minutes")
    
    st.subheader("ℹ️ System Info")
    st.text(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.text("Total PoE: 89")
    st.text("RPC: Online (Demo)")

# Demo ledger table
st.subheader("📜 Demo Blockchain Ledger")
import pandas as pd

demo_ledger = [
    {"poe_hash": "0x1a2b3c4d...", "tx_hash": "0x9876543...", "block_number": 1234565, "status": "confirmed", "created_at": "2025-10-22 14:30"},
    {"poe_hash": "0x5e6f7g8h...", "tx_hash": "0x8765432...", "block_number": 1234564, "status": "confirmed", "created_at": "2025-10-22 14:28"}, 
    {"poe_hash": "0x9i0j1k2l...", "tx_hash": "Pending", "block_number": None, "status": "pending", "created_at": "2025-10-22 14:32"},
]

df = pd.DataFrame(demo_ledger)
st.dataframe(df, use_container_width=True)

st.info("🎉 GentleΩ HeadQuarter Dashboard - Ready for production with real database!")
