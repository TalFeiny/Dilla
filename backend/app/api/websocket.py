"""
WebSocket support for real-time communication
"""

from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List, Optional, Any
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and store WebSocket connection"""
        await websocket.accept()
        
        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        
        self.active_connections[client_id].append(websocket)
        self.user_connections[f"{client_id}_{id(websocket)}"] = websocket
        
        logger.info(f"Client {client_id} connected via WebSocket")
        
        # Send welcome message
        await self.send_personal_message(
            {
                "type": "connection",
                "message": "Connected to Dilla AI WebSocket",
                "timestamp": datetime.now().isoformat()
            },
            websocket
        )
    
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove WebSocket connection"""
        if client_id in self.active_connections:
            if websocket in self.active_connections[client_id]:
                self.active_connections[client_id].remove(websocket)
            
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        
        # Remove from user connections
        connection_key = f"{client_id}_{id(websocket)}"
        if connection_key in self.user_connections:
            del self.user_connections[connection_key]
        
        logger.info(f"Client {client_id} disconnected from WebSocket")
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_client(self, message: Dict, client_id: str):
        """Send message to all connections of a specific client"""
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to client {client_id}: {e}")
    
    async def broadcast_all(self, message: Dict):
        """Broadcast message to all connected clients"""
        for client_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to all: {e}")


# Global connection manager
manager = ConnectionManager()


class WebSocketService:
    """Service for handling WebSocket operations"""
    
    def __init__(self):
        self.manager = manager
        self.active_tasks: Dict[str, asyncio.Task] = {}
    
    async def handle_message(self, websocket: WebSocket, client_id: str, data: Dict):
        """Handle incoming WebSocket messages"""
        message_type = data.get("type")
        
        if message_type == "ping":
            await self.handle_ping(websocket)
        
        elif message_type == "subscribe":
            await self.handle_subscription(websocket, client_id, data)
        
        elif message_type == "unsubscribe":
            await self.handle_unsubscription(client_id, data)
        
        elif message_type == "analysis_request":
            await self.handle_analysis_request(websocket, client_id, data)
        
        elif message_type == "progress_check":
            await self.handle_progress_check(websocket, client_id, data)
        
        elif message_type == "mcp":
            # Handle MCP-related messages
            from app.services.mcp_websocket import mcp_websocket_handler
            await mcp_websocket_handler.handle_mcp_message(websocket, client_id, data)
        
        else:
            await self.manager.send_personal_message(
                {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.now().isoformat()
                },
                websocket
            )
    
    async def handle_ping(self, websocket: WebSocket):
        """Handle ping message"""
        await self.manager.send_personal_message(
            {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            },
            websocket
        )
    
    async def handle_subscription(self, websocket: WebSocket, client_id: str, data: Dict):
        """Handle subscription requests"""
        channel = data.get("channel")
        
        if channel == "portfolio_updates":
            # Start sending portfolio updates
            task = asyncio.create_task(
                self.send_portfolio_updates(client_id, data.get("portfolio_id"))
            )
            self.active_tasks[f"{client_id}_portfolio"] = task
        
        elif channel == "market_data":
            # Start sending market data
            task = asyncio.create_task(
                self.send_market_updates(client_id, data.get("sectors", []))
            )
            self.active_tasks[f"{client_id}_market"] = task
        
        await self.manager.send_personal_message(
            {
                "type": "subscribed",
                "channel": channel,
                "timestamp": datetime.now().isoformat()
            },
            websocket
        )
    
    async def handle_unsubscription(self, client_id: str, data: Dict):
        """Handle unsubscription requests"""
        channel = data.get("channel")
        task_key = f"{client_id}_{channel}"
        
        if task_key in self.active_tasks:
            self.active_tasks[task_key].cancel()
            del self.active_tasks[task_key]
    
    async def handle_analysis_request(self, websocket: WebSocket, client_id: str, data: Dict):
        """Handle real-time analysis requests"""
        analysis_type = data.get("analysis_type")
        
        # Start analysis and stream progress
        asyncio.create_task(
            self.stream_analysis_progress(websocket, client_id, analysis_type, data)
        )
    
    async def handle_progress_check(self, websocket: WebSocket, client_id: str, data: Dict):
        """Check progress of ongoing operations"""
        task_id = data.get("task_id")
        
        # Send current progress
        await self.manager.send_personal_message(
            {
                "type": "progress",
                "task_id": task_id,
                "progress": 50,  # Mock progress
                "status": "processing",
                "timestamp": datetime.now().isoformat()
            },
            websocket
        )
    
    async def send_portfolio_updates(self, client_id: str, portfolio_id: Optional[str]):
        """Send periodic portfolio updates"""
        while True:
            try:
                # Mock portfolio update
                update = {
                    "type": "portfolio_update",
                    "portfolio_id": portfolio_id,
                    "data": {
                        "total_value": 125000000,
                        "change_24h": 2.5,
                        "top_performers": ["Company A", "Company B"]
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                await self.manager.broadcast_to_client(update, client_id)
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending portfolio updates: {e}")
                break
    
    async def send_market_updates(self, client_id: str, sectors: List[str]):
        """Send periodic market updates"""
        while True:
            try:
                # Mock market update
                update = {
                    "type": "market_update",
                    "sectors": sectors,
                    "data": {
                        "indices": {
                            "sp500": 4500.25,
                            "nasdaq": 14250.80
                        },
                        "sector_performance": {
                            sector: 1.5 for sector in sectors
                        }
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                await self.manager.broadcast_to_client(update, client_id)
                await asyncio.sleep(60)  # Update every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending market updates: {e}")
                break
    
    async def stream_analysis_progress(
        self,
        websocket: WebSocket,
        client_id: str,
        analysis_type: str,
        data: Dict
    ):
        """Stream analysis progress in real-time"""
        try:
            # Initial status
            await self.manager.send_personal_message(
                {
                    "type": "analysis_started",
                    "analysis_type": analysis_type,
                    "task_id": f"task_{datetime.now().timestamp()}",
                    "timestamp": datetime.now().isoformat()
                },
                websocket
            )
            
            # Simulate progress updates
            for progress in [10, 30, 50, 70, 90, 100]:
                await asyncio.sleep(2)
                
                await self.manager.send_personal_message(
                    {
                        "type": "analysis_progress",
                        "analysis_type": analysis_type,
                        "progress": progress,
                        "status": "completed" if progress == 100 else "processing",
                        "timestamp": datetime.now().isoformat()
                    },
                    websocket
                )
            
            # Final result
            await self.manager.send_personal_message(
                {
                    "type": "analysis_complete",
                    "analysis_type": analysis_type,
                    "result": {
                        "summary": "Analysis completed successfully",
                        "data": {}
                    },
                    "timestamp": datetime.now().isoformat()
                },
                websocket
            )
            
        except Exception as e:
            logger.error(f"Error streaming analysis progress: {e}")
            await self.manager.send_personal_message(
                {
                    "type": "analysis_error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                websocket
            )


# Global WebSocket service
websocket_service = WebSocketService()