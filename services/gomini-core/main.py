import os
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/gomini-core.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GOmini-AI Core",
    description="Hybrid inference engine for GentleΩ system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    model_name: Optional[str] = None

class InferenceResponse(BaseModel):
    response: str
    model_used: str
    tokens_generated: int
    inference_time: float

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    models_loaded: List[str]
    gpu_available: bool
    memory_usage: Dict[str, Any]

class ModelManager:
    def __init__(self):
        self.models = {}
        self.tokenizers = {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
    async def load_model(self, model_name: str):
        """Load a model and tokenizer"""
        try:
            if model_name not in self.models:
                logger.info(f"Loading model: {model_name}")
                
                # Load tokenizer
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    cache_dir="/app/models/huggingface"
                )
                
                # Load model with quantization if GPU available
                if torch.cuda.is_available():
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        torch_dtype=torch.float16,
                        device_map="auto",
                        cache_dir="/app/models/huggingface"
                    )
                else:
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        cache_dir="/app/models/huggingface"
                    )
                
                self.models[model_name] = model
                self.tokenizers[model_name] = tokenizer
                logger.info(f"Model {model_name} loaded successfully")
                
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")
    
    async def generate_response(self, request: InferenceRequest) -> InferenceResponse:
        """Generate response using loaded model"""
        start_time = time.time()
        
        # Default to a lightweight model if none specified
        model_name = request.model_name or "microsoft/DialoGPT-small"
        
        # Load model if not already loaded
        if model_name not in self.models:
            await self.load_model(model_name)
        
        try:
            model = self.models[model_name]
            tokenizer = self.tokenizers[model_name]
            
            # Tokenize input
            inputs = tokenizer.encode(request.prompt, return_tensors="pt").to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = model.generate(
                    inputs,
                    max_new_tokens=request.max_tokens,
                    temperature=request.temperature,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            # Decode response
            response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove the input prompt from response
            if response_text.startswith(request.prompt):
                response_text = response_text[len(request.prompt):].strip()
            
            inference_time = time.time() - start_time
            tokens_generated = len(outputs[0]) - len(inputs[0])
            
            return InferenceResponse(
                response=response_text,
                model_used=model_name,
                tokens_generated=tokens_generated,
                inference_time=inference_time
            )
            
        except Exception as e:
            logger.error(f"Error during inference: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

# Initialize model manager
model_manager = ModelManager()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        memory_info = {}
        if torch.cuda.is_available():
            memory_info = {
                "gpu_memory_allocated": torch.cuda.memory_allocated(),
                "gpu_memory_cached": torch.cuda.memory_reserved(),
                "gpu_memory_total": torch.cuda.get_device_properties(0).total_memory
            }
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            models_loaded=list(model_manager.models.keys()),
            gpu_available=torch.cuda.is_available(),
            memory_usage=memory_info
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")

@app.get("/models")
async def list_models():
    """List available and loaded models"""
    return {
        "loaded_models": list(model_manager.models.keys()),
        "device": str(model_manager.device),
        "gpu_available": torch.cuda.is_available()
    }

@app.get("/metrics")
async def get_metrics():
    """Get system metrics"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "models_loaded": len(model_manager.models),
        "gpu_available": torch.cuda.is_available(),
        "device": str(model_manager.device)
    }
    
    if torch.cuda.is_available():
        metrics.update({
            "gpu_memory_allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024,
            "gpu_memory_cached_mb": torch.cuda.memory_reserved() / 1024 / 1024,
            "gpu_utilization": torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 0
        })
    
    return metrics

@app.post("/inference", response_model=InferenceResponse)
async def generate_inference(request: InferenceRequest):
    """Generate inference response"""
    logger.info(f"Inference request: {request.prompt[:50]}...")
    
    try:
        response = await model_manager.generate_response(request)
        logger.info(f"Inference completed in {response.inference_time:.2f}s")
        return response
    except Exception as e:
        logger.error(f"Inference failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/load_model")
async def load_model_endpoint(model_name: str):
    """Load a specific model"""
    try:
        await model_manager.load_model(model_name)
        return {"status": "success", "message": f"Model {model_name} loaded successfully"}
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("GOMINI_PORT", 8505))
    host = os.getenv("GOMINI_HOST", "0.0.0.0")
    
    logger.info(f"Starting GOmini-AI Core on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )