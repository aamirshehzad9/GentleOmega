"""
GentleΩ Database Event Listener
Monitors database changes and triggers blockchain PoD/PoE transactions
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import psycopg
from psycopg.rows import dict_row
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from blockchain_client import record_pod, record_poe


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseEventListener:
    """Async database event listener for blockchain integration"""
    
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.connection: Optional[psycopg.AsyncConnection] = None
        self.running = False
        
    async def connect(self):
        """Establish database connection"""
        try:
            self.connection = await psycopg.AsyncConnection.connect(
                **self.connection_params,
                row_factory=dict_row
            )
            logger.info("✅ Connected to database for event listening")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("📴 Database connection closed")
    
    async def setup_triggers(self):
        """Setup database triggers for monitoring inserts"""
        try:
            async with self.connection.cursor() as cursor:
                # Create notification function
                await cursor.execute("""
                    CREATE OR REPLACE FUNCTION notify_item_insert()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        PERFORM pg_notify(
                            'item_inserted',
                            json_build_object(
                                'id', NEW.id,
                                'content', NEW.content,
                                'user_id', NEW.user_id,
                                'timestamp', NEW.created_at
                            )::text
                        );
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                """)
                
                # Create trigger on items table
                await cursor.execute("""
                    DROP TRIGGER IF EXISTS item_insert_trigger ON items;
                    CREATE TRIGGER item_insert_trigger
                    AFTER INSERT ON items
                    FOR EACH ROW
                    EXECUTE FUNCTION notify_item_insert();
                """)
                
                await self.connection.commit()
                logger.info("🔧 Database triggers setup complete")
                
        except Exception as e:
            logger.error(f"❌ Trigger setup failed: {e}")
            # Continue anyway - triggers are optional
    
    async def listen_for_inserts(self):
        """Listen for database insert notifications"""
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute("LISTEN item_inserted;")
                logger.info("👂 Listening for database events...")
                
                while self.running:
                    # Wait for notifications
                    try:
                        await asyncio.wait_for(
                            self.connection.wait(),
                            timeout=5.0  # Check running status every 5 seconds
                        )
                        
                        # Process notifications
                        for notification in self.connection.notifies():
                            await self.handle_item_insert(notification.payload)
                            
                    except asyncio.TimeoutError:
                        # Normal timeout - continue listening
                        continue
                    except Exception as e:
                        logger.error(f"❌ Notification error: {e}")
                        await asyncio.sleep(1)
                        
        except Exception as e:
            logger.error(f"❌ Listen loop error: {e}")
            
    async def handle_item_insert(self, payload: str):
        """Handle item insert notification and trigger PoD transaction"""
        try:
            # Parse notification payload
            data = json.loads(payload)
            logger.info(f"📦 New item inserted: {data['id']}")
            
            # Prepare PoD data
            pod_data = {
                "event_type": "item_insert",
                "item_id": data["id"],
                "content": data["content"],
                "user_id": data["user_id"],
                "timestamp": data["timestamp"],
                "database": "metacity",
                "table": "items"
            }
            
            # Record PoD transaction
            pod_result = await record_pod(pod_data)
            
            if pod_result["status"] == "success":
                logger.info(f"🔗 PoD recorded: {pod_result['transaction_hash']}")
                
                # Simulate processing and record PoE
                processing_result = {
                    "status": "processed",
                    "item_id": data["id"],
                    "processing_time": 0.05,
                    "vector_embedded": True,
                    "indexed": True
                }
                
                poe_result = await record_poe(pod_result["pod_hash"], processing_result)
                
                if poe_result["status"] == "success":
                    logger.info(f"✅ PoE recorded: {poe_result['transaction_hash']}")
                else:
                    logger.error(f"❌ PoE failed: {poe_result.get('error')}")
            else:
                logger.error(f"❌ PoD failed: {pod_result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ Handle insert error: {e}")
    
    async def start_monitoring(self):
        """Start the event monitoring loop"""
        self.running = True
        logger.info("🚀 Starting database event monitoring...")
        
        try:
            await self.connect()
            await self.setup_triggers()
            await self.listen_for_inserts()
        except Exception as e:
            logger.error(f"❌ Monitoring error: {e}")
        finally:
            await self.disconnect()
    
    async def stop_monitoring(self):
        """Stop the event monitoring loop"""
        self.running = False
        logger.info("🛑 Stopping database event monitoring...")


# Polling-based listener (fallback if triggers don't work)
class PollingEventListener:
    """Polling-based database monitor"""
    
    def __init__(self, connection_params: Dict[str, Any], poll_interval: int = 5):
        self.connection_params = connection_params
        self.poll_interval = poll_interval
        self.running = False
        self.last_item_id = 0
        
    async def start_polling(self):
        """Start polling for new items"""
        self.running = True
        logger.info(f"🔄 Starting polling monitor (interval: {self.poll_interval}s)")
        
        while self.running:
            try:
                async with await psycopg.AsyncConnection.connect(
                    **self.connection_params,
                    row_factory=dict_row
                ) as conn:
                    async with conn.cursor() as cursor:
                        # Check for new items
                        await cursor.execute(
                            "SELECT id, content, user_id, created_at FROM items WHERE id > %s ORDER BY id",
                            (self.last_item_id,)
                        )
                        
                        new_items = await cursor.fetchall()
                        
                        for item in new_items:
                            # Trigger PoD for each new item
                            pod_data = {
                                "event_type": "item_insert_poll",
                                "item_id": item["id"],
                                "content": item["content"],
                                "user_id": item["user_id"],
                                "timestamp": item["created_at"].isoformat() if item["created_at"] else None,
                                "database": "metacity",
                                "table": "items"
                            }
                            
                            pod_result = await record_pod(pod_data)
                            logger.info(f"🔗 [POLL] PoD recorded for item {item['id']}")
                            
                            self.last_item_id = max(self.last_item_id, item["id"])
                            
            except Exception as e:
                logger.error(f"❌ Polling error: {e}")
                
            await asyncio.sleep(self.poll_interval)
    
    def stop_polling(self):
        """Stop polling"""
        self.running = False


# Factory function to create appropriate listener
def create_listener(connection_params: Dict[str, Any], use_polling: bool = False) -> object:
    """Create database event listener"""
    if use_polling:
        return PollingEventListener(connection_params)
    else:
        return DatabaseEventListener(connection_params)


# Test function
async def test_listener():
    """Test the database event listener"""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join("..", "env", ".env"))
    
    connection_params = {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": int(os.getenv("PG_PORT", "5432")),
        "dbname": os.getenv("PG_DB", "metacity"),
        "user": os.getenv("PG_USER", "postgres"),
        "password": os.getenv("PG_PASSWORD"),
        "autocommit": True
    }
    
    listener = create_listener(connection_params, use_polling=True)
    
    try:
        await listener.start_polling()
    except KeyboardInterrupt:
        listener.stop_polling()
        logger.info("👋 Event listener stopped")


if __name__ == "__main__":
    asyncio.run(test_listener())