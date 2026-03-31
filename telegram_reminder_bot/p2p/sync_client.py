"""
P2P Sync Client for encrypted data synchronization
"""
import asyncio
import json
import hashlib
import hmac
import logging
import uuid
from typing import Optional
import aiohttp
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import P2P_SECRET
from storage.json_storage import storage
from utils.timezone import now_str

logger = logging.getLogger(__name__)


class P2PSyncClient:
    """
    P2P Sync Client for syncing encrypted data with remote server
    
    All data remains encrypted during transfer - server never sees plaintext.
    """
    
    def __init__(self, server_url: str, secret: str = P2P_SECRET):
        self.server_url = server_url.rstrip('/')
        self.secret = secret.encode() if secret else b""
        self.peer_id = str(uuid.uuid4())[:8]
        self._last_sync: dict = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_auth_headers(self) -> dict:
        """Generate authentication headers"""
        if not self.secret:
            return {}
        
        timestamp = now_str()
        signature = hmac.new(
            self.secret,
            timestamp.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'X-Auth-Timestamp': timestamp,
            'X-Auth-Signature': signature
        }
    
    async def push(self, user_id: int) -> dict:
        """
        Push local encrypted data to server
        
        Returns: {"status": "success"|"conflict"|"error", ...}
        """
        try:
            session = await self._get_session()
            
            # Get encrypted data
            encrypted_data = storage.export_data(user_id)
            if not encrypted_data:
                return {"status": "error", "message": "No local data to push"}
            
            headers = self._get_auth_headers()
            headers['Content-Type'] = 'application/json'
            
            async with session.post(
                f"{self.server_url}/sync/push",
                json={
                    "user_id": user_id,
                    "data": encrypted_data,
                    "version": self._last_sync.get(user_id, ""),
                    "peer_id": self.peer_id
                },
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("status") == "success":
                    self._last_sync[user_id] = result.get("version", "")
                
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"Push sync error: {e}")
            return {"status": "error", "message": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Push sync error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def pull(self, user_id: int) -> dict:
        """
        Pull encrypted data from server
        
        Returns: {"status": "success"|"up_to_date"|"no_data"|"error", ...}
        """
        try:
            session = await self._get_session()
            
            headers = self._get_auth_headers()
            headers['Content-Type'] = 'application/json'
            
            async with session.post(
                f"{self.server_url}/sync/pull",
                json={
                    "user_id": user_id,
                    "version": self._last_sync.get(user_id, "")
                },
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("status") == "success":
                    # Import encrypted data
                    encrypted_data = result.get("data")
                    if encrypted_data:
                        success = await storage.import_data(user_id, encrypted_data)
                        if success:
                            self._last_sync[user_id] = result.get("version", "")
                            return {"status": "success", "message": "Data synced successfully"}
                        else:
                            return {"status": "error", "message": "Failed to import data"}
                
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"Pull sync error: {e}")
            return {"status": "error", "message": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Pull sync error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def sync(self, user_id: int) -> dict:
        """
        Full sync - pull then push
        
        This ensures we have latest data before pushing our changes.
        """
        # First pull
        pull_result = await self.pull(user_id)
        
        if pull_result.get("status") == "error":
            return pull_result
        
        # Then push
        push_result = await self.push(user_id)
        
        return {
            "status": "success" if push_result.get("status") == "success" else push_result.get("status"),
            "pull": pull_result,
            "push": push_result
        }
    
    async def get_status(self, user_id: int) -> dict:
        """Get sync status from server"""
        try:
            session = await self._get_session()
            
            headers = self._get_auth_headers()
            headers['Content-Type'] = 'application/json'
            
            async with session.post(
                f"{self.server_url}/sync/status",
                json={"user_id": user_id},
                headers=headers
            ) as response:
                return await response.json()
                
        except Exception as e:
            logger.error(f"Status error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def health_check(self) -> bool:
        """Check if server is healthy"""
        try:
            session = await self._get_session()
            
            async with session.get(
                f"{self.server_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                result = await response.json()
                return result.get("status") == "ok"
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
