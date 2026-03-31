"""
Purpose: JWT-based authentication utilities for the DSS Coordinator.
Responsibilities:
    - Issue signed JWT tokens for authenticated peer nodes and the admin dashboard.
    - Decode and validate incoming JWT tokens.
    - Provide a FastAPI dependency that extracts and verifies the bearer token.
    - Expose create_admin_token() for issuing dashboard-scoped tokens.
    - Export ADMIN_SUBJECT so route handlers can identify admin callers.
Dependencies: python-jose, fastapi, dss.server.app.core.config
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from dss.server.app.core.config import Settings, get_settings

_bearer_scheme = HTTPBearer()

ADMIN_SUBJECT = "__admin__"


def create_access_token(node_id: str, settings: Settings) -> str:
    """
    Create a signed JWT access token for a peer node.
    Token payload includes sub (node_id) and exp (expiry timestamp).
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": node_id, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_admin_token(settings: Settings) -> str:
    """
    Create a signed JWT token for the DSS Admin Dashboard.
    Uses the reserved subject ADMIN_SUBJECT to distinguish it from peer tokens.
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": ADMIN_SUBJECT, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> Optional[str]:
    """
    Decode and validate a JWT access token.
    Returns the sub claim on success, or None if invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def require_peer_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    FastAPI dependency that validates the bearer token and returns the sub claim.
    Accepts both peer tokens and admin dashboard tokens.
    Raises HTTP 401 if the token is missing, malformed, or expired.
    """
    sub = decode_access_token(credentials.credentials, settings)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="DSS: invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return sub
