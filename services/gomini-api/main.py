import os
import asyncio
import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import jwt
import socketio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/gomini-api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GOmini-AI API",
    description="HTTP + SignalR bridge for AITB/UI integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")

# SocketIO server
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode='asgi'
)
socketio_app = socketio.ASGIApp(sio, app)

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    model_preference: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    model_used: str
    timestamp: str
    session_id: str

class SearchQuery(BaseModel):
    query: str
    collection: str = "default"
    n_results: int = 5

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]

class APIManager:
    def __init__(self):
        self.core_url = os.getenv("GOMINI_CORE_URL", "http://gomini-core:8505")
        self.vector_url = os.getenv("GOMINI_VECTOR_URL", "http://gomini-vector:8506")
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def check_services(self):
        """Check health of connected services"""
        services = {}
        
        try:
            # Check core service
            response = await self.client.get(f"{self.core_url}/health")
            services["core"] = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            services["core"] = "unreachable"
        
        try:
            # Check vector service
            response = await self.client.get(f"{self.vector_url}/health")
            services["vector"] = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            services["vector"] = "unreachable"
        
        return services
    
    async def generate_response(self, message: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate response using core service"""
        try:
            payload = {
                "prompt": message,
                "max_tokens": 512,
                "temperature": 0.7
            }
            
            if model_name:
                payload["model_name"] = model_name
            
            response = await self.client.post(
                f"{self.core_url}/inference",
                json=payload
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
    
    async def search_memory(self, query: str, collection: str = "default", n_results: int = 5) -> Dict[str, Any]:
        """Search vector memory"""
        try:
            payload = {
                "query": query,
                "collection_name": collection,
                "n_results": n_results
            }
            
            response = await self.client.post(
                f"{self.vector_url}/search",
                json=payload
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error searching memory: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")

# Initialize API manager
api_manager = APIManager()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify JWT token"""
    if not os.getenv("AUTH_REQUIRED", "true").lower() == "true":
        return {"user_id": "anonymous"}
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        services = await api_manager.check_services()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            services=services
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, user: dict = Depends(verify_token)):
    """Chat endpoint with AI inference"""
    try:
        logger.info(f"Chat request from user {user.get('user_id', 'anonymous')}: {message.message[:50]}...")
        
        # Generate response using core service
        inference_result = await api_manager.generate_response(
            message.message,
            message.model_preference
        )
        
        session_id = message.session_id or f"session_{datetime.now().timestamp()}"
        
        response = ChatResponse(
            response=inference_result["response"],
            model_used=inference_result["model_used"],
            timestamp=datetime.now().isoformat(),
            session_id=session_id
        )
        
        # Broadcast to connected clients via SocketIO
        await sio.emit('chat_response', {
            "session_id": session_id,
            "response": response.response,
            "model_used": response.model_used,
            "timestamp": response.timestamp
        })
        
        return response
        
    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_memory(query: SearchQuery, user: dict = Depends(verify_token)):
    """Search semantic memory"""
    try:
        logger.info(f"Memory search from user {user.get('user_id', 'anonymous')}: {query.query[:50]}...")
        
        result = await api_manager.search_memory(
            query.query,
            query.collection,
            query.n_results
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Memory search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/token")
async def create_token(user_id: str):
    """Create JWT token for authentication"""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

# SocketIO events
@sio.event
async def connect(sid, environ, auth):
    logger.info(f"Client connected: {sid}")
    await sio.emit('status', {'message': 'Connected to GOmini-AI'}, room=sid)

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def chat_message(sid, data):
    try:
        message = data.get('message', '')
        model_preference = data.get('model_preference')
        
        # Generate response
        inference_result = await api_manager.generate_response(message, model_preference)
        
        # Send response back to client
        await sio.emit('chat_response', {
            "response": inference_result["response"],
            "model_used": inference_result["model_used"],
            "timestamp": datetime.now().isoformat()
        }, room=sid)
        
    except Exception as e:
        logger.error(f"SocketIO chat error: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8507))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    logger.info(f"Starting GOmini-AI API on {host}:{port}")
    
    uvicorn.run(
        "main:socketio_app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )