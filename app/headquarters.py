"""
GentleΩ HeadQuarter - Visual Dashboard & Control Center
Streamlit-based monitoring dashboard for blockchain integration and memory operations
"""

import streamlit as st
import requests
import pandas as pd
import time
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

# Database connection detection
DATABASE_URL = os.getenv("DATABASE_URL")
PG_HOST = os.getenv("PG_HOST")
PG_USER = os.getenv("PG_USER") 
PG_DB = os.getenv("PG_DB")
PG_PASSWORD = os.getenv("PG_PASSWORD")

DB_CONNECTED = bool(DATABASE_URL or (PG_HOST and PG_USER and PG_DB and PG_PASSWORD))

# Page config
st.set_page_config(
    page_title="GentleΩ HeadQuarter",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration - Production URLs
API_BASE = "http://127.0.0.1:8000"
API_HEALTH = f"{API_BASE}/health"
API_STATUS = f"{API_BASE}/chain/status"
API_METRICS = f"{API_BASE}/chain/metrics"
API_LEDGER = f"{API_BASE}/chain/ledger?limit=10"
API_LOGS = f"{API_BASE}/logs/recent?lines=20"

def get_api_data(endpoint, default=None):
    """Safely fetch data from API endpoint"""
    try:
        response = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error {response.status_code}: {endpoint}")
            return default or {}
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return default or {}

def post_api_data(endpoint, data=None):
    """Safely post to API endpoint"""
    try:
        response = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error {response.status_code}: {endpoint}")
            return {"status": "error", "message": "API call failed"}
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return {"status": "error", "message": str(e)}

def main():
    # Header
    st.title("🧠 GentleΩ HeadQuarter")
    st.markdown("*Memory-Augmented AI Orchestrator with Blockchain Proofs*")
    
    # Database status indicator
    if DB_CONNECTED:
        st.success("🟢 Connected to live blockchain database")
    else:
        st.error("❌ Database not reachable - Check PostgreSQL connection")
    
    # Sidebar Controls
    with st.sidebar:
        st.header("🎛️ Control Panel")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto Refresh (10s)", value=True)
        
        # Manual refresh button
        if st.button("🔄 Refresh Now"):
            st.rerun()
        
        # Manual chain cycle trigger
        st.subheader("Chain Operations")
        if st.button("🔗 Trigger Chain Cycle"):
            with st.spinner("Running chain cycle..."):
                result = post_api_data("/chain/cycle")
                if result.get("status") == "success":
                    st.success("Chain cycle completed!")
                else:
                    st.error(f"Chain cycle failed: {result.get('message', 'Unknown error')}")
        
        # Health check
        st.subheader("System Health")
        health = get_api_data("/health", {"status": "unknown"})
        status = health.get("status", "unknown")
        if status == "healthy":
            st.success("✅ System Healthy")
        else:
            st.error("❌ System Issues")
    
    # Main Dashboard Layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Chain Status Overview
        st.subheader("🔗 Blockchain Status")
        
        chain_status = get_api_data("/chain/status")
        metrics = get_api_data("/chain/metrics")
        
        if chain_status and metrics:
            # Create metrics cards
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            
            with metric_col1:
                current_block = metrics.get("current_block", -1)
                st.metric("Current Block", current_block)
            
            with metric_col2:
                confirmed_block = metrics.get("last_confirmed_block", -1)
                st.metric("Last Confirmed", confirmed_block)
            
            with metric_col3:
                ledger_total = metrics.get("ledger_total", 0)
                st.metric("Ledger Entries", ledger_total)
            
            with metric_col4:
                rpc_ok = metrics.get("rpc_connectivity", False)
                latency = metrics.get("rpc_latency_ms", 0)
                st.metric("RPC Latency", f"{latency:.1f}ms" if rpc_ok else "Offline")
            
            # Sync status indicator
            synced = metrics.get("blockchain_synced", False)
            if synced:
                st.success("🟢 Blockchain Synchronized")
            else:
                gap = current_block - confirmed_block if current_block > 0 and confirmed_block > 0 else "Unknown"
                st.warning(f"🟡 Sync Gap: {gap} blocks")
        
        # PoE Status Distribution
        if metrics and "status_counts" in metrics:
            st.subheader("📊 PoE Status Distribution")
            
            status_counts = metrics["status_counts"]
            if status_counts:
                # Create pie chart
                fig = px.pie(
                    values=list(status_counts.values()),
                    names=list(status_counts.keys()),
                    title="Proof of Execution Status Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No PoE entries found")
    
    with col2:
        # Recent Logs
        st.subheader("📋 Recent Logs")
        
        logs_data = get_api_data("/logs/recent?lines=20")
        if logs_data and "logs" in logs_data:
            logs = logs_data["logs"]
            if logs:
                # Display logs in a scrollable container
                log_container = st.container()
                with log_container:
                    for log in reversed(logs[-10:]):  # Show last 10 lines
                        if "ERROR" in log:
                            st.error(log)
                        elif "WARNING" in log:
                            st.warning(log)
                        elif "INFO" in log:
                            st.info(log)
                        else:
                            st.text(log)
            else:
                st.info("No logs available")
        
        # System Info
        st.subheader("ℹ️ System Info")
        if metrics:
            last_updated = metrics.get("last_updated")
            if last_updated:
                st.text(f"Last Update: {last_updated[:19]}")
            
            total_entries = metrics.get("ledger_total", 0)
            st.text(f"Total PoE: {total_entries}")
            
            rpc_status = "Online" if metrics.get("rpc_connectivity") else "Offline"
            st.text(f"RPC: {rpc_status}")
    
    # Ledger Table (Full Width)
    st.subheader("📜 Recent Blockchain Ledger")
    
    ledger_data = get_api_data("/chain/ledger?limit=10")
    if ledger_data and "ledger" in ledger_data:
        ledger = ledger_data["ledger"]
        if ledger:
            # Convert to DataFrame for better display
            df = pd.DataFrame(ledger)
            
            # Format columns for display
            display_df = df[["poe_hash", "tx_hash", "block_number", "status", "created_at"]].copy()
            display_df["poe_hash"] = display_df["poe_hash"].str[:12] + "..."
            display_df["tx_hash"] = display_df["tx_hash"].apply(
                lambda x: x[:12] + "..." if x else "Pending"
            )
            display_df["created_at"] = pd.to_datetime(display_df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            
            # Style the dataframe
            def style_status(status):
                if status == "confirmed":
                    return "background-color: #d4edda; color: #155724;"
                elif status == "pending":
                    return "background-color: #fff3cd; color: #856404;"
                elif status == "failed":
                    return "background-color: #f8d7da; color: #721c24;"
                else:
                    return ""
            
            styled_df = display_df.style.applymap(style_status, subset=["status"])
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("No ledger entries found")
    
    # Performance Timeline (if we have historical data)
    st.subheader("📈 Performance Timeline")
    
    # For now, create a sample timeline - in production this would pull historical metrics
    timeline_data = []
    now = datetime.now()
    for i in range(24):  # Last 24 hours
        timestamp = now - timedelta(hours=i)
        # Mock data - replace with actual historical metrics
        timeline_data.append({
            "timestamp": timestamp,
            "confirmed_blocks": confirmed_block - (i * 2) if confirmed_block > 0 else 0,
            "rpc_latency": 100 + (i * 5),  # Mock increasing latency over time
        })
    
    if timeline_data:
        df_timeline = pd.DataFrame(timeline_data)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_timeline["timestamp"],
            y=df_timeline["confirmed_blocks"],
            mode="lines+markers",
            name="Confirmed Blocks",
            line=dict(color="green")
        ))
        
        fig.update_layout(
            title="Blockchain Synchronization Over Time",
            xaxis_title="Time",
            yaxis_title="Block Number",
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(10)
        st.rerun()

if __name__ == "__main__":
    main()