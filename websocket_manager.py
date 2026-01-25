"""
WebSocket Manager for real-time updates
"""
import asyncio
import json
from typing import Dict, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        # Active connections: {client_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # User to connections mapping for authenticated users
        self.user_connections: Dict[int, Set[str]] = {}
        self._connection_counter = 0

    def _generate_client_id(self) -> str:
        """Generate unique client ID"""
        self._connection_counter += 1
        return f"client_{self._connection_counter}_{datetime.utcnow().timestamp()}"

    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None) -> str:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        client_id = self._generate_client_id()
        self.active_connections[client_id] = websocket

        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(client_id)

        logger.info(f"WebSocket connected: {client_id} (user: {user_id})")
        return client_id

    def disconnect(self, client_id: str, user_id: Optional[int] = None):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(client_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        logger.info(f"WebSocket disconnected: {client_id}")

    async def send_personal_message(self, message: dict, client_id: str):
        """Send message to a specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {client_id}: {e}")
                self.disconnect(client_id)

    async def send_to_user(self, message: dict, user_id: int):
        """Send message to all connections of a specific user"""
        if user_id in self.user_connections:
            disconnected = []
            for client_id in self.user_connections[user_id]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending to user {user_id} ({client_id}): {e}")
                        disconnected.append(client_id)

            # Cleanup disconnected clients
            for client_id in disconnected:
                self.disconnect(client_id, user_id)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)

        # Cleanup disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)

    def get_user_connection_count(self, user_id: int) -> int:
        """Get number of connections for a specific user"""
        if user_id in self.user_connections:
            return len(self.user_connections[user_id])
        return 0


# Singleton instance
ws_manager = ConnectionManager()


# Event types for WebSocket messages
class WSEventType:
    # Bot events
    BOT_STATUS_CHANGED = "bot_status_changed"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"

    # Account events
    ACCOUNT_ADDED = "account_added"
    ACCOUNT_UPDATED = "account_updated"
    ACCOUNT_DELETED = "account_deleted"
    ACCOUNT_STATUS_CHANGED = "account_status_changed"

    # Order events
    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    ORDER_DELETED = "order_deleted"
    ORDER_OUTBID = "order_outbid"

    # System events
    ERROR = "error"
    NOTIFICATION = "notification"
    PING = "ping"
    PONG = "pong"


def create_ws_message(event_type: str, data: Any = None, message: str = None) -> dict:
    """Create a standardized WebSocket message"""
    msg = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat()
    }
    if data is not None:
        msg["data"] = data
    if message is not None:
        msg["message"] = message
    return msg


# Helper functions for broadcasting specific events
async def broadcast_bot_status(is_running: bool, check_interval: int = None):
    """Broadcast bot status change"""
    await ws_manager.broadcast(create_ws_message(
        WSEventType.BOT_STATUS_CHANGED,
        data={
            "is_running": is_running,
            "check_interval": check_interval
        }
    ))


async def broadcast_account_update(account_id: int, status: str, error_message: str = None):
    """Broadcast account status update"""
    await ws_manager.broadcast(create_ws_message(
        WSEventType.ACCOUNT_STATUS_CHANGED,
        data={
            "account_id": account_id,
            "status": status,
            "error_message": error_message
        }
    ))


async def broadcast_order_outbid(
    order_id: str,
    market_hash_name: str,
    old_price: int,
    new_price: int,
    competitor_price: int
):
    """Broadcast order outbid event"""
    await ws_manager.broadcast(create_ws_message(
        WSEventType.ORDER_OUTBID,
        data={
            "order_id": order_id,
            "market_hash_name": market_hash_name,
            "old_price_cents": old_price,
            "new_price_cents": new_price,
            "competitor_price_cents": competitor_price
        },
        message=f"Outbid: {market_hash_name} ${old_price/100:.2f} -> ${new_price/100:.2f}"
    ))


async def broadcast_notification(message: str, level: str = "info"):
    """Broadcast a notification to all clients"""
    await ws_manager.broadcast(create_ws_message(
        WSEventType.NOTIFICATION,
        data={"level": level},
        message=message
    ))
