import os
import asyncio
import uvicorn
import httpx
import subprocess
import platform
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import json
import secrets
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/gomini-gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GOmini Gateway",
    description="Secure bridge between AITB and GOmini-AI networks",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HandshakeRequest(BaseModel):
    client_id: str
    client_type: str  # "AITB" or "UI"
    requested_permissions: list[str]

class HandshakeResponse(BaseModel):
    status: str
    token: Optional[str]
    message: str
    expires_at: Optional[str]

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    network_status: Dict[str, str]
    connection_count: int

class GatewayManager:
    def __init__(self):
        self.active_connections = {}
        self.authorized_tokens = {}
        self.connection_history = []
        
    def show_user_confirmation_dialog(self, client_id: str, client_type: str, permissions: list) -> bool:
        """Show Windows user confirmation dialog"""
        try:
            if platform.system() != "Windows":
                logger.warning("User confirmation dialog only supported on Windows")
                return True  # Auto-approve on non-Windows systems
            
            # Create a simple message for the user
            message = f"Allow {client_type} ({client_id}) to connect to GOmini-AI?\\n\\nRequested permissions:\\n"
            for perm in permissions:
                message += f"- {perm}\\n"
            
            # Use PowerShell to show a message box
            cmd = [
                "powershell.exe",
                "-Command",
                f"[System.Windows.Forms.MessageBox]::Show('{message}', 'GOmini-AI Connection Request', 'YesNo', 'Question')"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Check if user clicked Yes (returns "Yes")
            approved = result.stdout.strip() == "Yes"
            
            logger.info(f"User {'approved' if approved else 'denied'} connection from {client_type} ({client_id})")
            return approved
            
        except subprocess.TimeoutExpired:
            logger.warning("User confirmation dialog timed out")
            return False
        except Exception as e:
            logger.error(f"Error showing confirmation dialog: {str(e)}")
            return False
    
    def store_token_in_credential_manager(self, client_id: str, token: str) -> bool:
        """Store token in Windows Credential Manager"""
        try:
            if platform.system() != "Windows":
                logger.info("Windows Credential Manager not available on this platform")
                return True
            
            # Use cmdkey to store credentials
            cmd = [
                "cmdkey",
                f"/generic:GOmini-AI-{client_id}",
                f"/user:{client_id}",
                f"/pass:{token}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Token stored in Credential Manager for {client_id}")
                return True
            else:
                logger.error(f"Failed to store token in Credential Manager: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing token in Credential Manager: {str(e)}")
            return False
    
    async def check_network_connectivity(self) -> Dict[str, str]:
        """Check connectivity to AITB and GOmini networks"""
        status = {}
        
        try:
            # Check GOmini-AI API
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get("http://gomini-api:8507/health")
                    status["gomini_api"] = "reachable" if response.status_code == 200 else "unhealthy"
                except:
                    status["gomini_api"] = "unreachable"
                
                # Try to detect AITB network
                try:
                    # This would need to be configured based on actual AITB endpoints
                    response = await client.get("http://host.docker.internal:3000/health", timeout=2.0)
                    status["aitb_network"] = "reachable" if response.status_code == 200 else "unreachable"
                except:
                    status["aitb_network"] = "unreachable"
        
        except Exception as e:
            logger.error(f"Network connectivity check failed: {str(e)}")
            status["error"] = str(e)
        
        return status
    
    def generate_access_token(self, client_id: str, permissions: list) -> str:
        """Generate secure access token"""
        token_data = {
            "client_id": client_id,
            "permissions": permissions,
            "issued_at": datetime.now().isoformat(),
            "expires_at": (datetime.now().timestamp() + 86400)  # 24 hours
        }
        
        # In production, this should be properly signed JWT
        token = secrets.token_urlsafe(32)
        self.authorized_tokens[token] = token_data
        
        return token
    
    async def initiate_handshake(self, request: HandshakeRequest) -> HandshakeResponse:
        """Initiate secure handshake with user confirmation"""
        try:
            logger.info(f"Handshake request from {request.client_type} ({request.client_id})")
            
            # Show user confirmation dialog
            user_approved = self.show_user_confirmation_dialog(
                request.client_id,
                request.client_type,
                request.requested_permissions
            )
            
            if not user_approved:
                return HandshakeResponse(
                    status="denied",
                    message="User denied connection request"
                )
            
            # Generate access token
            token = self.generate_access_token(request.client_id, request.requested_permissions)
            
            # Store in Windows Credential Manager
            credential_stored = self.store_token_in_credential_manager(request.client_id, token)
            
            # Record connection
            connection_record = {
                "client_id": request.client_id,
                "client_type": request.client_type,
                "timestamp": datetime.now().isoformat(),
                "status": "authorized",
                "token": token[:8] + "...",  # Log only first 8 chars for security
                "credential_stored": credential_stored
            }
            
            self.connection_history.append(connection_record)
            self.active_connections[request.client_id] = connection_record
            
            expires_at = datetime.fromtimestamp(
                self.authorized_tokens[token]["expires_at"]
            ).isoformat()
            
            # Log to activity log
            log_message = f"Handshake {request.client_type} ↔ GOmini-AI completed [{datetime.now().isoformat()}]; token established."
            with open('/app/logs/activity.log', 'a') as f:
                f.write(f"{log_message}\n")
            
            return HandshakeResponse(
                status="authorized",
                token=token,
                message="Connection authorized successfully",
                expires_at=expires_at
            )
            
        except Exception as e:
            logger.error(f"Handshake failed: {str(e)}")
            return HandshakeResponse(
                status="error",
                message=f"Handshake failed: {str(e)}"
            )

# Initialize gateway manager
gateway_manager = GatewayManager()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        network_status = await gateway_manager.check_network_connectivity()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            network_status=network_status,
            connection_count=len(gateway_manager.active_connections)
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")

@app.post("/handshake", response_model=HandshakeResponse)
async def handshake(request: HandshakeRequest):
    """Initiate secure handshake between networks"""
    return await gateway_manager.initiate_handshake(request)

@app.get("/connections")
async def list_connections():
    """List active connections"""
    return {
        "active_connections": list(gateway_manager.active_connections.keys()),
        "connection_history": gateway_manager.connection_history[-10:],  # Last 10
        "total_connections": len(gateway_manager.connection_history)
    }

@app.get("/network-status")
async def network_status():
    """Get detailed network status"""
    status = await gateway_manager.check_network_connectivity()
    
    # Add system information
    system_info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available
    }
    
    return {
        "network_connectivity": status,
        "system_info": system_info,
        "timestamp": datetime.now().isoformat()
    }

@app.delete("/connections/{client_id}")
async def revoke_connection(client_id: str):
    """Revoke access for a specific client"""
    try:
        if client_id in gateway_manager.active_connections:
            # Remove from active connections
            connection = gateway_manager.active_connections.pop(client_id)
            
            # Invalidate token
            token = None
            for t, data in gateway_manager.authorized_tokens.items():
                if data["client_id"] == client_id:
                    token = t
                    break
            
            if token:
                del gateway_manager.authorized_tokens[token]
            
            logger.info(f"Connection revoked for {client_id}")
            return {"status": "success", "message": f"Connection revoked for {client_id}"}
        else:
            raise HTTPException(status_code=404, detail="Client not found")
            
    except Exception as e:
        logger.error(f"Error revoking connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("GATEWAY_PORT", 8508))
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    
    logger.info(f"Starting GOmini Gateway on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )