"""
Authentication and authorization middleware
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
from app.core.config import settings
from app.core.database import supabase_service

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthService:
    """Handles authentication and authorization"""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM if hasattr(settings, 'ALGORITHM') else "HS256"
        self.access_token_expire = settings.ACCESS_TOKEN_EXPIRE_MINUTES if hasattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES') else 30
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> Dict[str, Any]:
        """Get current user from token"""
        token = credentials.credentials
        
        try:
            payload = self.verify_token(token)
            user_id = payload.get("sub")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Get user from database
            user = await self._get_user_by_id(user_id)
            
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def _get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from database by ID"""
        try:
            client = supabase_service.get_client()
            if not client:
                logger.error("Database unavailable — cannot authenticate user %s", user_id)
                return None
            
            response = client.table("users").select("*").eq("id", user_id).execute()
            
            if response.data:
                return response.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None
    
    async def verify_api_key(self, api_key: str) -> bool:
        """Verify API key"""
        try:
            # In production, check against database
            # For now, check against environment variable
            valid_keys = [
                settings.OPENAI_API_KEY,
                settings.ANTHROPIC_API_KEY,
            ]
            
            return api_key in valid_keys
            
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return False
    
    def check_permissions(
        self,
        user: Dict[str, Any],
        required_role: Optional[str] = None,
        required_permissions: Optional[List[str]] = None
    ) -> bool:
        """Check if user has required role or permissions"""
        if required_role:
            user_role = user.get("role", "user")
            role_hierarchy = ["user", "admin", "superadmin"]
            
            if user_role not in role_hierarchy:
                return False
            
            if required_role not in role_hierarchy:
                return False
            
            user_level = role_hierarchy.index(user_role)
            required_level = role_hierarchy.index(required_role)
            
            if user_level < required_level:
                return False
        
        if required_permissions:
            user_permissions = user.get("permissions", [])
            for permission in required_permissions:
                if permission not in user_permissions:
                    return False
        
        return True


# Singleton instance
auth_service = AuthService()


# Dependency functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get current user"""
    return await auth_service.get_current_user(credentials)


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Dependency to require admin role"""
    if not auth_service.check_permissions(current_user, required_role="admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Optional authentication - doesn't fail if no token
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Optional authentication - returns None if no valid token"""
    if not credentials:
        return None
    
    try:
        return await auth_service.get_current_user(credentials)
    except HTTPException:
        return None