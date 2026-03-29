"""
Purpose: Pydantic schema definitions for DSS peer entities.
Responsibilities: Define PeerInfo, PeerRegistration, and PeerStatus data shapes
    used across coordinator API boundaries and internal services.
Dependencies: pydantic
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PeerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class PeerRegistration(BaseModel):
    node_id: str = Field(..., description="Unique stable identifier derived from public key fingerprint")
    public_key_pem: str = Field(..., description="RSA-2048 public key in PEM format")
    host: str = Field(..., description="Advertised host or IP address")
    port: int = Field(..., ge=1024, le=65535)
    capacity_bytes: int = Field(..., ge=0)


class PeerInfo(BaseModel):
    node_id: str
    host: str
    port: int
    public_key_pem: str
    capacity_bytes: int
    used_bytes: int = 0
    status: PeerStatus = PeerStatus.ONLINE
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None

    class Config:
        use_enum_values = True


class HeartbeatRequest(BaseModel):
    node_id: str
    used_bytes: int = Field(..., ge=0)


class HeartbeatResponse(BaseModel):
    acknowledged: bool
    server_time: datetime = Field(default_factory=datetime.utcnow)
