"""
PostgreSQL to MSSQL Sync Module
Synchronizes GentleΩ data between PostgreSQL (primary) and MSSQL Server (backup)
"""

import os
import sys
sys.path.append(os.path.dirname(__file__))

import time
import pyodbc
import json
from datetime import datetime
from psycopg_fix import connect_pg
from dotenv import load_dotenv

# Load environment variables
load_dotenv("../env/.env")

# MSSQL Connection Configuration
MSSQL_SERVER = os.getenv("MSSQL_SERVER", "localhost\\SQLEXPRESS")
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE", "GentleOmega")
MSSQL_TRUSTED = os.getenv("MSSQL_TRUSTED_CONNECTION", "yes") == "yes"
MSSQL_USERNAME = os.getenv("MSSQL_USERNAME", "")
MSSQL_PASSWORD = os.getenv("MSSQL_PASSWORD", "")

# Sync configuration
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_MINUTES", "15"))  # 15 minute sync cycles
BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "1000"))

def get_mssql_connection():
    """Create MSSQL Server connection with Windows Authentication fallback"""
    try:
        if MSSQL_TRUSTED:
            # Windows Authentication (recommended for local development)
            conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={MSSQL_SERVER};DATABASE={MSSQL_DATABASE};Trusted_Connection=yes;"
        else:
            # SQL Server Authentication
            conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={MSSQL_SERVER};DATABASE={MSSQL_DATABASE};UID={MSSQL_USERNAME};PWD={MSSQL_PASSWORD};"
        
        conn = pyodbc.connect(conn_str, timeout=30)
        print(f"✅ Connected to MSSQL: {MSSQL_SERVER}/{MSSQL_DATABASE}")
        return conn
    except Exception as e:
        print(f"❌ MSSQL Connection Failed: {str(e)}")
        return None

def initialize_mssql_schema():
    """Create MSSQL tables matching PostgreSQL schema"""
    conn = get_mssql_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Create database if not exists (requires elevated permissions)
        try:
            cursor.execute(f"CREATE DATABASE [{MSSQL_DATABASE}]")
            print(f"Created database: {MSSQL_DATABASE}")
        except pyodbc.Error:
            pass  # Database likely already exists
        
        # Use the database
        cursor.execute(f"USE [{MSSQL_DATABASE}]")
        
        # Create blockchain_ledger table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='blockchain_ledger' AND xtype='U')
        CREATE TABLE blockchain_ledger (
            id INT IDENTITY(1,1) PRIMARY KEY,
            poe_hash NVARCHAR(66) NOT NULL UNIQUE,
            tx_hash NVARCHAR(66) NULL,
            block_number BIGINT NULL,
            status NVARCHAR(20) DEFAULT 'pending',
            gas_used BIGINT NULL,
            gas_price BIGINT NULL,
            created_at DATETIME2 DEFAULT GETUTCDATE(),
            updated_at DATETIME2 DEFAULT GETUTCDATE(),
            sync_timestamp DATETIME2 DEFAULT GETUTCDATE()
        )
        """)
        
        # Create pods_poe table  
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='pods_poe' AND xtype='U')
        CREATE TABLE pods_poe (
            id INT IDENTITY(1,1) PRIMARY KEY,
            pod_hash NVARCHAR(66) NOT NULL,
            poe_hash NVARCHAR(66) NOT NULL,
            content NTEXT NULL,
            metadata NTEXT NULL,
            created_at DATETIME2 DEFAULT GETUTCDATE(),
            sync_timestamp DATETIME2 DEFAULT GETUTCDATE()
        )
        """)
        
        # Create memories table (core RAG storage)
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='memories' AND xtype='U')
        CREATE TABLE memories (
            id INT IDENTITY(1,1) PRIMARY KEY,
            content NTEXT NOT NULL,
            embedding NTEXT NULL,  -- Store as JSON string
            importance FLOAT DEFAULT 0.5,
            user_id NVARCHAR(100) DEFAULT 'system',
            session_id NVARCHAR(100) NULL,
            tags NTEXT NULL,  -- JSON array as string
            metadata NTEXT NULL,  -- JSON object as string
            created_at DATETIME2 DEFAULT GETUTCDATE(),
            accessed_at DATETIME2 DEFAULT GETUTCDATE(),
            access_count INT DEFAULT 0,
            sync_timestamp DATETIME2 DEFAULT GETUTCDATE()
        )
        """)
        
        # Create sync tracking table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sync_status' AND xtype='U')
        CREATE TABLE sync_status (
            table_name NVARCHAR(100) PRIMARY KEY,
            last_sync_id INT DEFAULT 0,
            last_sync_timestamp DATETIME2 DEFAULT GETUTCDATE(),
            records_synced INT DEFAULT 0,
            sync_errors INT DEFAULT 0
        )
        """)
        
        # Initialize sync status for each table
        tables_to_track = ['blockchain_ledger', 'pods_poe', 'memories']
        for table in tables_to_track:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sync_status WHERE table_name = ?)
            INSERT INTO sync_status (table_name) VALUES (?)
            """, (table, table))
        
        conn.commit()
        print("✅ MSSQL Schema initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ MSSQL Schema initialization failed: {str(e)}")
        return False
    finally:
        conn.close()

def sync_table_to_mssql(table_name, pg_columns, mssql_columns=None):
    """Sync a single table from PostgreSQL to MSSQL"""
    if not mssql_columns:
        mssql_columns = pg_columns
    
    try:
        # Get PostgreSQL connection
        pg = connect_pg()
        if not pg:
            return False, "PostgreSQL connection failed"
        
        # Get MSSQL connection
        mssql_conn = get_mssql_connection()
        if not mssql_conn:
            return False, "MSSQL connection failed"
        
        mssql_cursor = mssql_conn.cursor()
        
        # Get last synced ID for this table
        mssql_cursor.execute("SELECT last_sync_id FROM sync_status WHERE table_name = ?", (table_name,))
        result = mssql_cursor.fetchone()
        last_sync_id = result[0] if result else 0
        
        # Fetch new records from PostgreSQL
        with pg.cursor() as pg_cursor:
            columns_str = ", ".join(pg_columns)
            pg_cursor.execute(f"""
                SELECT {columns_str}
                FROM {table_name}
                WHERE id > %s
                ORDER BY id
                LIMIT %s
            """, (last_sync_id, BATCH_SIZE))
            
            new_records = pg_cursor.fetchall()
        
        if not new_records:
            return True, "No new records to sync"
        
        # Insert new records into MSSQL
        synced_count = 0
        max_id = last_sync_id
        
        for record in new_records:
            try:
                # Handle special data types
                processed_record = []
                for i, value in enumerate(record):
                    if isinstance(value, dict) or isinstance(value, list):
                        # Convert dict/list to JSON string
                        processed_record.append(json.dumps(value))
                    elif isinstance(value, datetime):
                        # Ensure datetime is in correct format
                        processed_record.append(value)
                    else:
                        processed_record.append(value)
                
                # Build INSERT statement
                placeholders = ", ".join(["?" for _ in mssql_columns])
                insert_sql = f"INSERT INTO {table_name} ({', '.join(mssql_columns)}) VALUES ({placeholders})"
                
                mssql_cursor.execute(insert_sql, processed_record)
                synced_count += 1
                max_id = max(max_id, record[0])  # Assuming first column is ID
                
            except Exception as e:
                print(f"⚠️ Failed to sync record {record[0]} from {table_name}: {str(e)}")
                continue
        
        # Update sync status
        mssql_cursor.execute("""
            UPDATE sync_status 
            SET last_sync_id = ?, 
                last_sync_timestamp = GETUTCDATE(),
                records_synced = records_synced + ?
            WHERE table_name = ?
        """, (max_id, synced_count, table_name))
        
        mssql_conn.commit()
        
        return True, f"Synced {synced_count} records from {table_name}"
        
    except Exception as e:
        return False, f"Sync failed for {table_name}: {str(e)}"
    finally:
        if 'pg' in locals():
            pg.close()
        if 'mssql_conn' in locals():
            mssql_conn.close()

def sync_blockchain_ledger():
    """Sync blockchain_ledger table"""
    pg_columns = ['id', 'poe_hash', 'tx_hash', 'block_number', 'status', 'gas_used', 'gas_price', 'created_at', 'updated_at']
    mssql_columns = ['id', 'poe_hash', 'tx_hash', 'block_number', 'status', 'gas_used', 'gas_price', 'created_at', 'updated_at']
    
    return sync_table_to_mssql('blockchain_ledger', pg_columns, mssql_columns)

def sync_pods_poe():
    """Sync pods_poe table"""
    pg_columns = ['id', 'pod_hash', 'poe_hash', 'content', 'metadata', 'created_at']
    mssql_columns = ['id', 'pod_hash', 'poe_hash', 'content', 'metadata', 'created_at']
    
    return sync_table_to_mssql('pods_poe', pg_columns, mssql_columns)

def sync_memories():
    """Sync memories table (excluding vector embeddings for MSSQL compatibility)"""
    pg_columns = ['id', 'content', 'importance', 'user_id', 'session_id', 'tags', 'metadata', 'created_at', 'accessed_at', 'access_count']
    mssql_columns = ['id', 'content', 'importance', 'user_id', 'session_id', 'tags', 'metadata', 'created_at', 'accessed_at', 'access_count']
    
    return sync_table_to_mssql('memories', pg_columns, mssql_columns)

def run_full_sync():
    """Run complete synchronization cycle"""
    print(f"\n🔄 Starting PostgreSQL → MSSQL sync at {datetime.now().isoformat()}")
    
    sync_results = []
    
    # Sync each table
    tables_to_sync = [
        ('blockchain_ledger', sync_blockchain_ledger),
        ('pods_poe', sync_pods_poe),
        ('memories', sync_memories)
    ]
    
    for table_name, sync_func in tables_to_sync:
        print(f"Syncing {table_name}...")
        success, message = sync_func()
        sync_results.append({
            'table': table_name,
            'success': success,
            'message': message
        })
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
    
    # Summary
    successful_syncs = sum(1 for result in sync_results if result['success'])
    total_syncs = len(sync_results)
    
    print(f"\n📊 Sync Summary: {successful_syncs}/{total_syncs} tables synchronized successfully")
    
    return sync_results

def sync_daemon():
    """Continuous sync daemon - runs in background"""
    print(f"🤖 PostgreSQL→MSSQL Sync Daemon started (interval: {SYNC_INTERVAL} minutes)")
    
    # Initialize schema on startup
    if not initialize_mssql_schema():
        print("❌ Failed to initialize MSSQL schema. Exiting.")
        return
    
    while True:
        try:
            run_full_sync()
            print(f"⏰ Next sync in {SYNC_INTERVAL} minutes...")
            time.sleep(SYNC_INTERVAL * 60)  # Convert minutes to seconds
            
        except KeyboardInterrupt:
            print("\n🛑 Sync daemon stopped by user")
            break
        except Exception as e:
            print(f"❌ Sync daemon error: {str(e)}")
            print(f"⏰ Retrying in {SYNC_INTERVAL} minutes...")
            time.sleep(SYNC_INTERVAL * 60)

def test_connections():
    """Test both PostgreSQL and MSSQL connections"""
    print("🔍 Testing database connections...")
    
    # Test PostgreSQL
    try:
        pg = connect_pg()
        if pg:
            with pg.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM blockchain_ledger")
                pg_count = cur.fetchone()[0]
                print(f"✅ PostgreSQL: {pg_count} blockchain_ledger records")
            pg.close()
        else:
            print("❌ PostgreSQL: Connection failed")
    except Exception as e:
        print(f"❌ PostgreSQL: {str(e)}")
    
    # Test MSSQL
    try:
        mssql_conn = get_mssql_connection()
        if mssql_conn:
            cursor = mssql_conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM blockchain_ledger")
                mssql_count = cursor.fetchone()[0]
                print(f"✅ MSSQL: {mssql_count} blockchain_ledger records")
            except:
                print("⚠️ MSSQL: Connected but blockchain_ledger table not found (run initialization)")
            mssql_conn.close()
        else:
            print("❌ MSSQL: Connection failed")
    except Exception as e:
        print(f"❌ MSSQL: {str(e)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            test_connections()
        elif command == "init":
            initialize_mssql_schema()
        elif command == "sync":
            run_full_sync()
        elif command == "daemon":
            sync_daemon()
        else:
            print("Usage: python mssql_sync.py [test|init|sync|daemon]")
    else:
        print("🚀 GentleΩ PostgreSQL→MSSQL Sync Module")
        print("Commands:")
        print("  test   - Test database connections")
        print("  init   - Initialize MSSQL schema")
        print("  sync   - Run one-time sync")
        print("  daemon - Start continuous sync daemon")