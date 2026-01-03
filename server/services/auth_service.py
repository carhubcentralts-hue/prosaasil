"""
Authentication service for token management, idle timeout, and session handling
Production-grade implementation following SaaS best practices
"""
import os
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from flask import request
from server.models_sql import User, RefreshToken, db
from server.services.email_service import get_email_service

logger = logging.getLogger(__name__)

# Configuration constants
ACCESS_TOKEN_LIFETIME_MINUTES = 90  # Access token valid for 90 minutes
REFRESH_TOKEN_DEFAULT_DAYS = 1  # Default refresh token: 24 hours
REFRESH_TOKEN_REMEMBER_DAYS = 30  # With "remember me": 30 days
IDLE_TIMEOUT_MINUTES = 75  # Automatic logout after 75 minutes of inactivity
PASSWORD_RESET_TOKEN_MINUTES = 60  # Password reset token valid for 60 minutes

# Get public URL from environment
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'https://app.prosaas.co')

def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256 for secure storage
    
    Args:
        token: Plain token string
        
    Returns:
        str: Hex-encoded hash
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def hash_user_agent(user_agent: Optional[str]) -> Optional[str]:
    """
    Hash user agent string for security binding (normalized for browser updates)
    
    Args:
        user_agent: User agent string from request
        
    Returns:
        str: Hashed normalized user agent or None
    """
    if not user_agent:
        return None
    
    # Normalize: extract major browser/OS info only (ignore minor version changes)
    # Example: "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0.0" -> "Windows_Chrome"
    ua_lower = user_agent.lower()
    
    # Extract major parts
    parts = []
    if 'windows' in ua_lower:
        parts.append('windows')
    elif 'mac' in ua_lower or 'macos' in ua_lower:
        parts.append('mac')
    elif 'linux' in ua_lower:
        parts.append('linux')
    elif 'iphone' in ua_lower or 'ipad' in ua_lower:
        parts.append('ios')
    elif 'android' in ua_lower:
        parts.append('android')
    
    if 'chrome' in ua_lower and 'edg' not in ua_lower:
        parts.append('chrome')
    elif 'edg' in ua_lower:
        parts.append('edge')
    elif 'firefox' in ua_lower:
        parts.append('firefox')
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        parts.append('safari')
    
    normalized = '_'.join(parts) if parts else user_agent
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

class AuthService:
    """Authentication service for managing tokens and sessions"""
    
    @staticmethod
    def generate_refresh_token(
        user_id: int,
        tenant_id: Optional[int],
        remember_me: bool = False,
        user_agent: Optional[str] = None
    ) -> Tuple[str, RefreshToken]:
        """
        Generate a new refresh token for a user
        
        Args:
            user_id: User ID
            tenant_id: Tenant/Business ID
            remember_me: Whether to extend token lifetime
            user_agent: User agent string for security binding
            
        Returns:
            Tuple of (plain_token, RefreshToken object)
        """
        # Generate secure random token (32 bytes = 64 hex characters)
        plain_token = secrets.token_urlsafe(32)
        token_hash = hash_token(plain_token)
        
        # Calculate expiry based on remember_me
        if remember_me:
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_REMEMBER_DAYS)
        else:
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DEFAULT_DAYS)
        
        # Create refresh token record
        refresh_token = RefreshToken(
            user_id=user_id,
            tenant_id=tenant_id,
            token_hash=token_hash,
            user_agent_hash=hash_user_agent(user_agent),
            expires_at=expires_at,
            is_valid=True,
            remember_me=remember_me
        )
        
        db.session.add(refresh_token)
        db.session.commit()
        
        logger.info(f"[AUTH] refresh_issued user_id={user_id} remember_me={remember_me} exp={expires_at.isoformat()}")
        
        return plain_token, refresh_token
    
    @staticmethod
    def validate_refresh_token(
        plain_token: str,
        user_agent: Optional[str] = None,
        check_idle: bool = True
    ) -> Optional[RefreshToken]:
        """
        Validate a refresh token
        
        Args:
            plain_token: Plain token string
            user_agent: User agent string for security check
            check_idle: Whether to check idle timeout (default True)
            
        Returns:
            RefreshToken object if valid, None otherwise
        """
        token_hash = hash_token(plain_token)
        
        # Find token in database
        refresh_token = RefreshToken.query.filter_by(
            token_hash=token_hash,
            is_valid=True
        ).first()
        
        if not refresh_token:
            logger.warning(f"[AUTH] Refresh token not found or invalid")
            return None
        
        # Check if expired
        if refresh_token.is_expired():
            logger.warning(f"[AUTH] Refresh token expired user_id={refresh_token.user_id}")
            refresh_token.is_valid = False
            db.session.commit()
            return None
        
        # Check idle timeout (per-session)
        if check_idle and refresh_token.is_idle(IDLE_TIMEOUT_MINUTES):
            logger.info(f"[AUTH] idle_timeout_logout user_id={refresh_token.user_id} token_id={refresh_token.id}")
            refresh_token.is_valid = False
            db.session.commit()
            return None
        
        # Soft user agent verification (log but don't reject)
        if user_agent and refresh_token.user_agent_hash:
            current_ua_hash = hash_user_agent(user_agent)
            if current_ua_hash != refresh_token.user_agent_hash:
                logger.warning(
                    f"[AUTH] User agent mismatch for user_id={refresh_token.user_id} token_id={refresh_token.id} "
                    f"- browser may have updated (normalized UA changed)"
                )
                # Allow token but log for audit - handles browser updates
        
        # Update activity timestamp (per-session)
        refresh_token.last_activity_at = datetime.utcnow()
        refresh_token.last_used_at = datetime.utcnow()
        db.session.commit()
        
        return refresh_token
    
    @staticmethod
    def invalidate_refresh_token(token_hash: str) -> bool:
        """
        Invalidate a specific refresh token
        
        Args:
            token_hash: Hashed token
            
        Returns:
            bool: True if token was invalidated
        """
        refresh_token = RefreshToken.query.filter_by(token_hash=token_hash).first()
        if refresh_token:
            refresh_token.is_valid = False
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def invalidate_all_user_tokens(user_id: int) -> int:
        """
        Invalidate all refresh tokens for a user (logout all sessions)
        
        Args:
            user_id: User ID
            
        Returns:
            int: Number of tokens invalidated
        """
        count = RefreshToken.query.filter_by(
            user_id=user_id,
            is_valid=True
        ).update({'is_valid': False})
        db.session.commit()
        
        logger.info(f"[AUTH] all_sessions_invalidated user_id={user_id} count={count}")
        
        return count
    
    @staticmethod
    def update_token_activity(token_hash: str) -> bool:
        """
        Update refresh token activity timestamp (per-session tracking)
        
        Performance Note: This commits on every authenticated request.
        For very high-scale systems (>10k req/sec), consider:
        - Redis cache for activity tracking
        - Background worker batch updates (every 5-10 minutes)
        - Activity update only if last_activity_at > 5 minutes old
        
        Current approach is fine for typical SaaS scale (<1k req/sec per session).
        
        Args:
            token_hash: Hashed token
            
        Returns:
            bool: True if updated successfully
        """
        try:
            refresh_token = RefreshToken.query.filter_by(token_hash=token_hash).first()
            if refresh_token:
                # Optional optimization: only update if stale (reduces DB writes by ~10x)
                # if datetime.utcnow() - refresh_token.last_activity_at < timedelta(minutes=5):
                #     return True  # Skip update if recently updated
                
                refresh_token.last_activity_at = datetime.utcnow()
                db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"[AUTH] Failed to update token activity: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def generate_password_reset_token(email: str) -> bool:
        """
        Generate and send password reset token
        
        Args:
            email: User's email address
            
        Returns:
            bool: Always returns True (don't reveal if email exists)
        """
        # Find user by email
        user = User.query.filter_by(email=email, is_active=True).first()
        
        if user:
            # Generate secure reset token
            plain_token = secrets.token_urlsafe(32)
            token_hash = hash_token(plain_token)
            
            # Store hashed token in database
            user.reset_token_hash = token_hash
            user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES)
            user.reset_token_used = False
            db.session.commit()
            
            # Build reset URL
            reset_url = f"{PUBLIC_BASE_URL}/reset-password?token={plain_token}"
            
            # Send email
            email_service = get_email_service()
            email_sent = email_service.send_password_reset_email(
                to_email=user.email,
                reset_url=reset_url,
                user_name=user.name
            )
            
            logger.info(f"[AUTH] password_reset_requested email={email} sent={email_sent}")
        else:
            # User not found - log but don't reveal
            logger.info(f"[AUTH] password_reset_requested email={email} sent=false (user_not_found)")
        
        # Always return True to prevent email enumeration
        return True
    
    @staticmethod
    def validate_reset_token(plain_token: str) -> Optional[User]:
        """
        Validate password reset token
        
        Args:
            plain_token: Plain reset token
            
        Returns:
            User object if token is valid, None otherwise
        """
        token_hash = hash_token(plain_token)
        
        # Find user with this reset token
        user = User.query.filter_by(
            reset_token_hash=token_hash,
            is_active=True
        ).first()
        
        if not user:
            logger.warning(f"[AUTH] Invalid reset token")
            return None
        
        # Check if token is expired
        if user.reset_token_expiry < datetime.utcnow():
            logger.warning(f"[AUTH] Reset token expired for user_id={user.id}")
            return None
        
        # Check if token was already used
        if user.reset_token_used:
            logger.warning(f"[AUTH] Reset token already used for user_id={user.id}")
            return None
        
        return user
    
    @staticmethod
    def complete_password_reset(plain_token: str, new_password_hash: str) -> bool:
        """
        Complete password reset and invalidate all sessions
        
        Args:
            plain_token: Plain reset token
            new_password_hash: New password hash
            
        Returns:
            bool: True if reset was successful
        """
        user = AuthService.validate_reset_token(plain_token)
        
        if not user:
            return False
        
        # Update password
        user.password_hash = new_password_hash
        
        # Mark token as used
        user.reset_token_used = True
        
        # Clear reset token fields
        user.reset_token_hash = None
        user.reset_token_expiry = None
        
        db.session.commit()
        
        # Invalidate all refresh tokens (logout all sessions)
        AuthService.invalidate_all_user_tokens(user.id)
        
        logger.info(f"[AUTH] password_reset_completed user_id={user.id}")
        
        return True
    
    @staticmethod
    def cleanup_expired_tokens() -> int:
        """
        Clean up expired refresh tokens
        
        Returns:
            int: Number of tokens deleted
        """
        expired_tokens = RefreshToken.query.filter(
            RefreshToken.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
        
        if expired_tokens > 0:
            logger.info(f"[AUTH] Cleaned up {expired_tokens} expired refresh tokens")
        
        return expired_tokens

# Helper function to get user agent from request
def get_request_user_agent() -> Optional[str]:
    """Get user agent from current request"""
    return request.headers.get('User-Agent')
