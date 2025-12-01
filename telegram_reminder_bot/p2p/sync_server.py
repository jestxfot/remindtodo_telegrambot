"""
P2P Sync Server for encrypted data synchronization

This server allows multiple devices to sync encrypted JSON data.
All data remains encrypted - server never sees plaintext.
"""
import asyncio
import json
import hashlib
import hmac
import logging
from datetime import datetime
from typing import Dict, Optional, Set
from aiohttp import web
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import P2P_PORT, P2P_SECRET
from storage.json_storage import storage

logger = logging.getLogger(__name__)


class P2PSyncServer:
    """
    P2P Sync Server for encrypted data synchronization
    
    Features:
    - End-to-end encryption (server never sees plaintext)
    - HMAC authentication
    - Version conflict resolution
    - Multi-device sync
    """
    
    def __init__(self, port: int = P2P_PORT, secret: str = P2P_SECRET):
        self.port = port
        self.secret = secret.encode() if secret else b""
        self.app = web.Application()
        self._setup_routes()
        self._connected_peers: Dict[int, Set[str]] = {}  # user_id -> peer_ids
        self._last_sync: Dict[int, str] = {}  # user_id -> last_sync_timestamp
    
    def _setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_post('/sync/push', self.handle_push)
        self.app.router.add_post('/sync/pull', self.handle_pull)
        self.app.router.add_post('/sync/status', self.handle_status)
        self.app.router.add_get('/health', self.handle_health)
    
    def _verify_auth(self, request: web.Request) -> bool:
        """Verify HMAC authentication"""
        if not self.secret:
            return True  # No auth required if no secret set
        
        auth_header = request.headers.get('X-Auth-Signature', '')
        timestamp = request.headers.get('X-Auth-Timestamp', '')
        
        if not auth_header or not timestamp:
            return False
        
        # Verify timestamp is recent (within 5 minutes)
        try:
            ts = datetime.fromisoformat(timestamp)
            if abs((datetime.utcnow() - ts).total_seconds()) > 300:
                return False
        except ValueError:
            return False
        
        # Verify HMAC
        expected = hmac.new(
            self.secret,
            timestamp.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(auth_header, expected)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        return web.json_response({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "connected_users": len(self._connected_peers)
        })
    
    async def handle_push(self, request: web.Request) -> web.Response:
        """
        Handle push sync request
        
        Client pushes their encrypted data to server
        """
        if not self._verify_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        
        try:
            data = await request.json()
            user_id = data.get("user_id")
            encrypted_data = data.get("data")
            client_version = data.get("version", "")
            peer_id = data.get("peer_id", "unknown")
            
            if not user_id or not encrypted_data:
                return web.json_response({"error": "Missing required fields"}, status=400)
            
            # Check for conflicts
            server_version = self._last_sync.get(user_id, "")
            
            if server_version and server_version > client_version:
                # Server has newer data - conflict
                return web.json_response({
                    "status": "conflict",
                    "server_version": server_version,
                    "message": "Server has newer data. Pull first."
                }, status=409)
            
            # Save encrypted data
            success = await storage.import_data(user_id, encrypted_data)
            
            if success:
                new_version = datetime.utcnow().isoformat()
                self._last_sync[user_id] = new_version
                
                # Track peer
                if user_id not in self._connected_peers:
                    self._connected_peers[user_id] = set()
                self._connected_peers[user_id].add(peer_id)
                
                logger.info(f"Push sync successful for user {user_id} from peer {peer_id}")
                
                return web.json_response({
                    "status": "success",
                    "version": new_version,
                    "message": "Data synced successfully"
                })
            else:
                return web.json_response({"error": "Failed to save data"}, status=500)
                
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Push sync error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_pull(self, request: web.Request) -> web.Response:
        """
        Handle pull sync request
        
        Client pulls encrypted data from server
        """
        if not self._verify_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        
        try:
            data = await request.json()
            user_id = data.get("user_id")
            client_version = data.get("version", "")
            
            if not user_id:
                return web.json_response({"error": "Missing user_id"}, status=400)
            
            # Check if update needed
            server_version = self._last_sync.get(user_id, "")
            
            if client_version and client_version >= server_version:
                # Client is up to date
                return web.json_response({
                    "status": "up_to_date",
                    "version": server_version
                })
            
            # Get encrypted data
            encrypted_data = storage.export_data(user_id)
            
            if encrypted_data:
                return web.json_response({
                    "status": "success",
                    "version": server_version,
                    "data": encrypted_data
                })
            else:
                return web.json_response({
                    "status": "no_data",
                    "message": "No data found for this user"
                }, status=404)
                
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Pull sync error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_status(self, request: web.Request) -> web.Response:
        """Get sync status for user"""
        if not self._verify_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        
        try:
            data = await request.json()
            user_id = data.get("user_id")
            
            if not user_id:
                return web.json_response({"error": "Missing user_id"}, status=400)
            
            return web.json_response({
                "user_id": user_id,
                "last_sync": self._last_sync.get(user_id),
                "connected_peers": len(self._connected_peers.get(user_id, set())),
                "has_data": await storage.user_exists(user_id)
            })
            
        except Exception as e:
            logger.error(f"Status error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def start(self):
        """Start the P2P sync server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"P2P Sync server started on port {self.port}")
        return runner
    
    def run(self):
        """Run the server (blocking)"""
        web.run_app(self.app, port=self.port)
