from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import docker
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
import asyncio
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI MCP Hub Application
app = FastAPI(
    title="GOmini-AI MCP Hub",
    description="Model Context Protocol Hub for GentleΩ Workspace",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MODELS_PATH = os.getenv("MODELS_PATH", "/models")
LOGS_PATH = os.getenv("LOGS_PATH", "/logs")
MCP_PORT = int(os.getenv("MCP_PORT", "8600"))

# Docker client
try:
    docker_client = docker.from_env()
    logger.info("Docker client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Docker client: {e}")
    docker_client = None

# Pydantic models
class ModelInfo(BaseModel):
    name: str
    container_id: str
    status: str
    port: Optional[int] = None
    image: str
    created: str

class GenerateRequest(BaseModel):
    prompt: str
    model: str
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7

class GenerateResponse(BaseModel):
    response: str
    model: str
    timestamp: str
    cached: bool = False

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]
    models_registered: int

# Model registry
model_registry = {}
inference_cache = {}

def save_registry():
    """Save model registry to disk"""
    try:
        registry_path = os.path.join(LOGS_PATH, "mcp-model-registry.json")
        with open(registry_path, 'w') as f:
            json.dump(model_registry, f, indent=2)
        logger.info(f"Model registry saved to {registry_path}")
    except Exception as e:
        logger.error(f"Failed to save registry: {e}")

def load_registry():
    """Load model registry from disk"""
    global model_registry
    try:
        registry_path = os.path.join(LOGS_PATH, "mcp-model-registry.json")
        if os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                model_registry = json.load(f)
            logger.info(f"Model registry loaded from {registry_path}")
    except Exception as e:
        logger.error(f"Failed to load registry: {e}")

def detect_model_containers():
    """Detect existing model containers"""
    if not docker_client:
        return []
    
    model_containers = []
    model_images = ["gemma", "mistral", "qwen", "smollm", "ollama"]
    
    try:
        for container in docker_client.containers.list(all=True):
            image_name = container.image.tags[0] if container.image.tags else "unknown"
            container_name = container.name.lower()
            
            # Check if container is a known model
            for model in model_images:
                if model in image_name.lower() or model in container_name:
                    model_info = {
                        "name": container.name,
                        "container_id": container.id[:12],
                        "status": container.status,
                        "image": image_name,
                        "created": container.attrs["Created"][:19]
                    }
                    
                    # Try to extract port mapping
                    try:
                        if container.ports:
                            for port_config in container.ports.values():
                                if port_config:
                                    model_info["port"] = int(port_config[0]["HostPort"])
                                    break
                    except:
                        pass
                    
                    model_containers.append(model_info)
                    break
        
        logger.info(f"Detected {len(model_containers)} model containers")
        return model_containers
        
    except Exception as e:
        logger.error(f"Error detecting model containers: {e}")
        return []

@app.on_event("startup")
async def startup_event():
    """Initialize MCP Hub on startup"""
    logger.info("Starting GOmini-AI MCP Hub...")
    
    # Create logs directory if needed
    os.makedirs(LOGS_PATH, exist_ok=True)
    
    # Load existing registry
    load_registry()
    
    # Detect and register model containers
    model_containers = detect_model_containers()
    for model in model_containers:
        model_registry[model["name"]] = model
    
    # Save updated registry
    save_registry()
    
    logger.info(f"MCP Hub started with {len(model_registry)} models registered")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {
        "docker": "healthy" if docker_client else "unhealthy",
        "models_path": "healthy" if os.path.exists(MODELS_PATH) else "unhealthy",
        "logs_path": "healthy" if os.path.exists(LOGS_PATH) else "unhealthy"
    }
    
    return HealthResponse(
        status="healthy" if all(s == "healthy" for s in services.values()) else "degraded",
        timestamp=datetime.now().isoformat(),
        services=services,
        models_registered=len(model_registry)
    )

@app.get("/models", response_model=List[ModelInfo])
async def get_models():
    """Get list of registered models"""
    models = []
    for name, info in model_registry.items():
        models.append(ModelInfo(**info))
    return models

@app.post("/models/register")
async def register_model(model: ModelInfo):
    """Register a new model"""
    model_registry[model.name] = model.dict()
    save_registry()
    logger.info(f"Registered model: {model.name}")
    return {"status": "registered", "model": model.name}

@app.post("/models/scan")
async def scan_models():
    """Scan for new model containers"""
    model_containers = detect_model_containers()
    new_models = 0
    
    for model in model_containers:
        if model["name"] not in model_registry:
            model_registry[model["name"]] = model
            new_models += 1
    
    save_registry()
    logger.info(f"Scan completed: {new_models} new models found")
    return {"status": "completed", "new_models": new_models, "total_models": len(model_registry)}

@app.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """Generate text using specified model"""
    # Check cache first
    cache_key = f"{request.model}:{hash(request.prompt)}"
    if cache_key in inference_cache:
        cached_response = inference_cache[cache_key]
        logger.info(f"Returning cached response for {request.model}")
        return GenerateResponse(
            response=cached_response["response"],
            model=request.model,
            timestamp=datetime.now().isoformat(),
            cached=True
        )
    
    # Check if model exists
    if request.model not in model_registry:
        raise HTTPException(status_code=404, detail=f"Model {request.model} not found")
    
    model_info = model_registry[request.model]
    
    # Simulate inference (replace with actual model inference)
    try:
        # This would normally call the actual model container
        # For now, simulate response
        simulated_response = f"[{request.model}] Generated response for: {request.prompt[:50]}..."
        
        # Cache the response
        inference_cache[cache_key] = {
            "response": simulated_response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Limit cache size
        if len(inference_cache) > 1000:
            # Remove oldest entries
            oldest_keys = list(inference_cache.keys())[:100]
            for key in oldest_keys:
                del inference_cache[key]
        
        logger.info(f"Generated text using {request.model}")
        return GenerateResponse(
            response=simulated_response,
            model=request.model,
            timestamp=datetime.now().isoformat(),
            cached=False
        )
        
    except Exception as e:
        logger.error(f"Error generating text with {request.model}: {e}")
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

@app.get("/models/{model_name}/status")
async def get_model_status(model_name: str):
    """Get status of specific model"""
    if model_name not in model_registry:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
    
    model_info = model_registry[model_name]
    
    # Check container status if Docker client available
    if docker_client:
        try:
            container = docker_client.containers.get(model_info["container_id"])
            model_info["current_status"] = container.status
        except Exception as e:
            model_info["current_status"] = "unknown"
            logger.warning(f"Could not get container status: {e}")
    
    return model_info

@app.delete("/models/{model_name}")
async def unregister_model(model_name: str):
    """Unregister a model"""
    if model_name not in model_registry:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
    
    del model_registry[model_name]
    save_registry()
    logger.info(f"Unregistered model: {model_name}")
    return {"status": "unregistered", "model": model_name}

@app.get("/cache/stats")
async def get_cache_stats():
    """Get inference cache statistics"""
    return {
        "cache_size": len(inference_cache),
        "registry_size": len(model_registry),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/cache/clear")
async def clear_cache():
    """Clear inference cache"""
    global inference_cache
    cache_size = len(inference_cache)
    inference_cache = {}
    logger.info(f"Cleared inference cache ({cache_size} entries)")
    return {"status": "cleared", "entries_removed": cache_size}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)