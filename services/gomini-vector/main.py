import os
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/gomini-vector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GOmini-AI Vector",
    description="Semantic memory database for GentleΩ system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Document(BaseModel):
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str
    n_results: int = 5
    collection_name: str = "default"

class SearchResult(BaseModel):
    documents: List[Dict[str, Any]]
    similarities: List[float]
    total_results: int

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    collections: List[str]
    total_documents: int

class VectorManager:
    def __init__(self):
        self.client = None
        self.embedder = None
        self.collections = {}
        self.init_chroma()
        self.init_embedder()
    
    def init_chroma(self):
        """Initialize ChromaDB client"""
        try:
            persist_directory = os.getenv("PERSIST_DIRECTORY", "/app/vector_db")
            os.makedirs(persist_directory, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"ChromaDB initialized with persist directory: {persist_directory}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise
    
    def init_embedder(self):
        """Initialize sentence transformer for embeddings"""
        try:
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {str(e)}")
            raise
    
    def get_or_create_collection(self, collection_name: str):
        """Get or create a collection"""
        try:
            if collection_name not in self.collections:
                try:
                    collection = self.client.get_collection(collection_name)
                    logger.info(f"Retrieved existing collection: {collection_name}")
                except:
                    collection = self.client.create_collection(
                        name=collection_name,
                        metadata={"created_at": datetime.now().isoformat()}
                    )
                    logger.info(f"Created new collection: {collection_name}")
                
                self.collections[collection_name] = collection
            
            return self.collections[collection_name]
            
        except Exception as e:
            logger.error(f"Error with collection {collection_name}: {str(e)}")
            raise
    
    async def add_documents(self, documents: List[Document], collection_name: str = "default"):
        """Add documents to vector database"""
        try:
            collection = self.get_or_create_collection(collection_name)
            
            # Prepare data for insertion
            ids = [doc.id for doc in documents]
            contents = [doc.content for doc in documents]
            metadatas = [doc.metadata or {} for doc in documents]
            
            # Generate embeddings
            embeddings = self.embedder.encode(contents).tolist()
            
            # Add to collection
            collection.add(
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Added {len(documents)} documents to collection {collection_name}")
            return {"status": "success", "added": len(documents)}
            
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def search_documents(self, request: SearchRequest) -> SearchResult:
        """Search for similar documents"""
        try:
            collection = self.get_or_create_collection(request.collection_name)
            
            # Generate query embedding
            query_embedding = self.embedder.encode([request.query]).tolist()[0]
            
            # Search collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=request.n_results,
                include=['documents', 'metadatas', 'distances']
            )
            
            # Format results
            documents = []
            similarities = []
            
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    documents.append({
                        "id": results['ids'][0][i] if results['ids'] else f"doc_{i}",
                        "content": doc,
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0.0
                    })
                    
                    # Convert distance to similarity (lower distance = higher similarity)
                    similarity = 1.0 - (results['distances'][0][i] if results['distances'] else 0.0)
                    similarities.append(max(0.0, similarity))
            
            return SearchResult(
                documents=documents,
                similarities=similarities,
                total_results=len(documents)
            )
            
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_collection_stats(self):
        """Get statistics about all collections"""
        stats = {}
        total_docs = 0
        
        try:
            collections = self.client.list_collections()
            
            for collection in collections:
                count = collection.count()
                stats[collection.name] = count
                total_docs += count
            
            return {
                "collections": list(stats.keys()),
                "collection_stats": stats,
                "total_documents": total_docs
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "collections": [],
                "collection_stats": {},
                "total_documents": 0
            }

# Initialize vector manager
vector_manager = VectorManager()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        stats = vector_manager.get_collection_stats()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            collections=stats["collections"],
            total_documents=stats["total_documents"]
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")

@app.get("/collections")
async def list_collections():
    """List all collections and their statistics"""
    return vector_manager.get_collection_stats()

@app.post("/documents")
async def add_documents(documents: List[Document], collection_name: str = "default"):
    """Add documents to vector database"""
    return await vector_manager.add_documents(documents, collection_name)

@app.post("/search", response_model=SearchResult)
async def search_documents(request: SearchRequest):
    """Search for similar documents"""
    logger.info(f"Search request: {request.query[:50]}... in collection {request.collection_name}")
    return await vector_manager.search_documents(request)

@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection"""
    try:
        vector_manager.client.delete_collection(collection_name)
        if collection_name in vector_manager.collections:
            del vector_manager.collections[collection_name]
        
        return {"status": "success", "message": f"Collection {collection_name} deleted"}
    except Exception as e:
        logger.error(f"Error deleting collection {collection_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("VECTOR_PORT", 8506))
    host = os.getenv("VECTOR_HOST", "0.0.0.0")
    
    logger.info(f"Starting GOmini-AI Vector on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )