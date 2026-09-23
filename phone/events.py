# Phone Events - Structured models for phone notifications and messages

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PhoneEventType(Enum):
    NOTIFICATION = "notification"
    MESSAGE = "message"


@dataclass(frozen=True)
class PhoneEvent:
    """Base class for all phone events."""
    event_type: PhoneEventType
    device_id: str
    device_name: str
    timestamp: datetime
    event_id: str


@dataclass(frozen=True)
class NotificationEvent(PhoneEvent):
    """Android notification event from KDE Connect."""
    app_package: str
    app_name: str
    title: str
    body: str
    notification_id: str
    event_type: PhoneEventType = field(default=PhoneEventType.NOTIFICATION, init=False)


@dataclass(frozen=True)
class MessageEvent(PhoneEvent):
    """SMS/Message event from KDE Connect."""
    sender: str
    body: str
    message_id: str
    conversation_id: Optional[str] = None
    event_type: PhoneEventType = field(default=PhoneEventType.MESSAGE, init=False)


class PhoneEventError(Exception):
    """Base exception for phone event errors."""
    pass


class PhoneEventPermissionError(PermissionError):
    """Raised when phone event access is denied by permissions."""
    pass


class PhoneEventParseError(PhoneEventError):
    """Raised when phone event data cannot be parsed."""
    pass