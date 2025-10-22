"""
GentleΩ AI Orchestration Controller
Manages asyncio background tasks for PoD → PoE pipeline, embeddings, and blockchain integration
"""

import sys, os
sys.path.append(os.path.dirname(__file__))

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import hashlib
import time

from psycopg_fix import connect_pg
from blockchain_client import BlockchainClient, record_pod, record_poe, add_to_ledger, verify_chain_integrity
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join("env", ".env"))

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "metacity")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASSWORD", "postgres")

# Hugging Face configuration
HF_TOKEN = os.getenv("HF_TOKEN")
HF_API_BASE = os.getenv("HF_API_BASE", "https://api-inference.huggingface.co")
EMBEDDINGS_BACKEND = os.getenv("EMBEDDINGS_BACKEND", "local")


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrchestrationTask:
    id: str
    task_type: str
    data: Dict[str, Any]
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pod_hash: Optional[str] = None
    poe_hash: Optional[str] = None


class GentleOmegaOrchestrator:
    """Main orchestration controller for AI agent tasks and blockchain integration"""
    
    def __init__(self):
        self.is_running = False
        self.tasks_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, OrchestrationTask] = {}
        self.blockchain_client = BlockchainClient()
        self.pg_connection = None
        self.background_tasks = []
        
        # Health monitoring
        self.health_status = {
            "orchestrator": "initializing",
            "database": "unknown",
            "blockchain": "unknown",
            "embeddings": "unknown",
            "tasks_processed": 0,
            "errors_count": 0,
            "last_health_check": None
        }
        
        # Configuration
        self.max_concurrent_tasks = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
        self.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))  # seconds
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging for orchestration operations"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "agent_orchestration.log")
        
        # Configure logger
        self.logger = logging.getLogger("GentleOmegaOrchestrator")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers if not already added
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def get_db_connection(self):
        """Get database connection for orchestration operations"""
        if not self.pg_connection:
            self.pg_connection = connect_pg(PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS)
        return self.pg_connection
    
    async def start(self):
        """Start the orchestration system"""
        if self.is_running:
            self.logger.warning("Orchestrator is already running")
            return
        
        self.logger.info("Starting GentleΩ Orchestration Controller...")
        self.is_running = True
        self.health_status["orchestrator"] = "starting"
        
        try:
            # Test database connection
            await self.test_database_connection()
            
            # Verify blockchain integrity
            await self.test_blockchain_integrity()
            
            # Test embeddings backend
            await self.test_embeddings_backend()
            
            # Start background tasks
            await self.start_background_tasks()
            
            self.health_status["orchestrator"] = "running"
            self.logger.info("✅ GentleΩ Orchestration Controller started successfully")
            
        except Exception as e:
            self.health_status["orchestrator"] = "failed"
            self.logger.error(f"❌ Failed to start orchestrator: {e}")
            raise
    
    async def stop(self):
        """Stop the orchestration system"""
        if not self.is_running:
            return
        
        self.logger.info("Stopping GentleΩ Orchestration Controller...")
        self.is_running = False
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Close blockchain client
        await self.blockchain_client.close()
        
        self.health_status["orchestrator"] = "stopped"
        self.logger.info("GentleΩ Orchestration Controller stopped")
    
    async def test_database_connection(self):
        """Test database connectivity and setup"""
        try:
            pg = self.get_db_connection()
            with pg.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            
            self.health_status["database"] = "connected"
            self.logger.info("✅ Database connection verified")
            
        except Exception as e:
            self.health_status["database"] = "failed"
            self.logger.error(f"❌ Database connection failed: {e}")
            raise
    
    async def test_blockchain_integrity(self):
        """Test blockchain ledger integrity"""
        try:
            integrity_result = verify_chain_integrity()
            
            if integrity_result["status"] == "success":
                self.health_status["blockchain"] = "verified"
                self.logger.info(f"✅ Blockchain integrity verified: {integrity_result['entries']} entries, {integrity_result['verified']} verified")
            else:
                self.health_status["blockchain"] = "compromised"
                self.logger.error(f"❌ Blockchain integrity compromised: {integrity_result['broken_links']}")
                
        except Exception as e:
            self.health_status["blockchain"] = "error"
            self.logger.error(f"❌ Blockchain integrity check failed: {e}")
            raise
    
    async def test_embeddings_backend(self):
        """Test embeddings backend connectivity"""
        try:
            if EMBEDDINGS_BACKEND == "local":
                # Test local sentence transformers
                try:
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer('all-MiniLM-L6-v2')
                    test_embedding = model.encode(["test"])
                    self.health_status["embeddings"] = "local_ready"
                    self.logger.info("✅ Local embeddings model ready")
                except ImportError:
                    self.health_status["embeddings"] = "mock_mode"
                    self.logger.warning("⚠️ sentence-transformers not available, using mock embeddings")
            else:
                # Test remote embeddings API
                if HF_TOKEN:
                    self.health_status["embeddings"] = "remote_ready"
                    self.logger.info("✅ Remote embeddings configured")
                else:
                    self.health_status["embeddings"] = "no_token"
                    self.logger.warning("⚠️ HF_TOKEN not configured for remote embeddings")
                    
        except Exception as e:
            self.health_status["embeddings"] = "error"
            self.logger.error(f"❌ Embeddings backend test failed: {e}")
    
    async def start_background_tasks(self):
        """Start background asyncio tasks"""
        # Task processor
        task_processor = asyncio.create_task(self.process_tasks())
        self.background_tasks.append(task_processor)
        
        # Health monitor
        health_monitor = asyncio.create_task(self.health_monitoring_loop())
        self.background_tasks.append(health_monitor)
        
        # Blockchain integrity checker
        integrity_checker = asyncio.create_task(self.periodic_integrity_check())
        self.background_tasks.append(integrity_checker)
        
        self.logger.info("Background tasks started")
    
    async def process_tasks(self):
        """Main task processing loop"""
        self.logger.info("Task processor started")
        
        while self.is_running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.tasks_queue.get(), timeout=1.0)
                
                # Process task if we have capacity
                if len(self.active_tasks) < self.max_concurrent_tasks:
                    asyncio.create_task(self.execute_task(task))
                else:
                    # Put task back in queue if no capacity
                    await self.tasks_queue.put(task)
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                self.logger.error(f"Error in task processor: {e}")
                await asyncio.sleep(1)
    
    async def execute_task(self, task: OrchestrationTask):
        """Execute a specific orchestration task"""
        task_id = task.id
        self.active_tasks[task_id] = task
        
        try:
            self.logger.info(f"Processing task {task_id}: {task.task_type}")
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now(timezone.utc)
            
            # Execute based on task type
            if task.task_type == "create_item":
                result = await self.process_create_item_task(task)
            elif task.task_type == "generate_embedding":
                result = await self.process_embedding_task(task)
            elif task.task_type == "pod_poe_flow":
                result = await self.process_pod_poe_flow_task(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            # Mark task as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = result
            
            self.health_status["tasks_processed"] += 1
            self.logger.info(f"✅ Task {task_id} completed successfully")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            
            self.health_status["errors_count"] += 1
            self.logger.error(f"❌ Task {task_id} failed: {e}")
            
        finally:
            # Clean up active tasks
            self.active_tasks.pop(task_id, None)
    
    async def process_create_item_task(self, task: OrchestrationTask) -> Dict[str, Any]:
        """Process item creation with PoD → PoE flow"""
        data = task.data
        content = data.get("content")
        user_id = data.get("user_id")
        
        start_time = time.time()
        
        # Step 1: Record PoD
        pod_result = await record_pod({
            "task_type": "create_item",
            "content": content,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        task.pod_hash = pod_result.get("pod_hash")
        
        # Step 2: Execute the actual item creation
        pg = self.get_db_connection()
        with pg.cursor() as cur:
            cur.execute(
                "INSERT INTO items(content, user_id) VALUES (%s, %s) RETURNING id",
                (content, user_id)
            )
            result = cur.fetchone()
            item_id = result[0] if result else None
        
        # Step 3: Record PoE
        execution_result = {
            "status": "completed",
            "item_id": item_id,
            "content": content,
            "user_id": user_id,
            "processing_time": time.time() - start_time
        }
        
        poe_result = await record_poe(task.pod_hash, execution_result)
        task.poe_hash = poe_result.get("poe_hash")
        
        return {
            "item_id": item_id,
            "pod_result": pod_result,
            "poe_result": poe_result,
            "processing_time": time.time() - start_time
        }
    
    async def process_embedding_task(self, task: OrchestrationTask) -> Dict[str, Any]:
        """Process text embedding generation"""
        text = task.data.get("text")
        
        if EMBEDDINGS_BACKEND == "local":
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('all-MiniLM-L6-v2')
                embedding = model.encode([text])[0].tolist()
            except ImportError:
                # Mock embedding
                embedding = [0.1] * 384
        else:
            # Mock remote embedding for now
            embedding = [0.1] * 384
        
        return {
            "text": text,
            "embedding": embedding,
            "dimension": len(embedding),
            "backend": EMBEDDINGS_BACKEND
        }
    
    async def process_pod_poe_flow_task(self, task: OrchestrationTask) -> Dict[str, Any]:
        """Process generic PoD → PoE flow task"""
        data = task.data
        
        # Record PoD
        pod_result = await record_pod(data)
        task.pod_hash = pod_result.get("pod_hash")
        
        # Simulate processing
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Record PoE
        execution_result = {
            "status": "completed",
            "processed_data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        poe_result = await record_poe(task.pod_hash, execution_result)
        task.poe_hash = poe_result.get("poe_hash")
        
        return {
            "pod_result": pod_result,
            "poe_result": poe_result,
            "execution_result": execution_result
        }
    
    async def health_monitoring_loop(self):
        """Background health monitoring"""
        self.logger.info("Health monitoring started")
        
        while self.is_running:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Update health status
                self.health_status["last_health_check"] = datetime.now(timezone.utc).isoformat()
                
                # Log health summary
                active_count = len(self.active_tasks)
                queue_size = self.tasks_queue.qsize()
                
                self.logger.info(
                    f"Health Check - Active: {active_count}, Queue: {queue_size}, "
                    f"Processed: {self.health_status['tasks_processed']}, "
                    f"Errors: {self.health_status['errors_count']}"
                )
                
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
    
    async def periodic_integrity_check(self):
        """Periodic blockchain integrity verification"""
        self.logger.info("Periodic integrity checker started")
        
        # Check every 10 minutes
        check_interval = 600
        
        while self.is_running:
            try:
                await asyncio.sleep(check_interval)
                
                integrity_result = verify_chain_integrity()
                if integrity_result["status"] == "success":
                    self.logger.info(f"Integrity check passed: {integrity_result['entries']} entries verified")
                else:
                    self.logger.warning(f"Integrity check issues: {integrity_result['broken_links']}")
                    
            except Exception as e:
                self.logger.error(f"Periodic integrity check error: {e}")
    
    def submit_task(self, task_type: str, data: Dict[str, Any]) -> str:
        """Submit a new task for processing"""
        task_id = hashlib.sha256(
            f"{task_type}_{datetime.now().isoformat()}_{hash(str(data))}".encode()
        ).hexdigest()[:16]
        
        task = OrchestrationTask(
            id=task_id,
            task_type=task_type,
            data=data,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        # Submit to queue (non-blocking)
        asyncio.create_task(self.tasks_queue.put(task))
        
        self.logger.info(f"Task submitted: {task_id} ({task_type})")
        return task_id
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current orchestration health status"""
        return {
            **self.health_status,
            "active_tasks": len(self.active_tasks),
            "queue_size": self.tasks_queue.qsize(),
            "uptime": self.is_running
        }


# Global orchestrator instance
orchestrator = GentleOmegaOrchestrator()

# Convenience functions
async def start_orchestration():
    """Start the global orchestration system"""
    await orchestrator.start()

async def stop_orchestration():
    """Stop the global orchestration system"""
    await orchestrator.stop()

def submit_create_item_task(content: str, user_id: str) -> str:
    """Submit item creation task"""
    return orchestrator.submit_task("create_item", {"content": content, "user_id": user_id})

def submit_embedding_task(text: str) -> str:
    """Submit text embedding task"""
    return orchestrator.submit_task("generate_embedding", {"text": text})

def submit_pod_poe_task(data: Dict[str, Any]) -> str:
    """Submit generic PoD → PoE task"""
    return orchestrator.submit_task("pod_poe_flow", data)

def get_orchestration_health() -> Dict[str, Any]:
    """Get orchestration health status"""
    return orchestrator.get_health_status()


if __name__ == "__main__":
    async def test_orchestrator():
        """Test the orchestrator"""
        print("Testing GentleΩ Orchestrator...")
        
        await start_orchestration()
        
        # Submit test tasks
        task1 = submit_create_item_task("Test item from orchestrator", "test_user")
        task2 = submit_embedding_task("Hello GentleOmega!")
        task3 = submit_pod_poe_task({"test_data": "orchestration_test"})
        
        print(f"Submitted tasks: {task1}, {task2}, {task3}")
        
        # Wait for processing
        await asyncio.sleep(5)
        
        # Check health
        health = get_orchestration_health()
        print(f"Health Status: {health}")
        
        await stop_orchestration()
        print("Orchestrator test completed")
    
    asyncio.run(test_orchestrator())