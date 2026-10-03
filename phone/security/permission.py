# this handles the permission access of the app - phone = mac

# importing the nessary modules
from enum import Enum


# class for permission
class PhonePermision(str, Enum):
    Status = "status"
    NOTIFICATIONS = "notifications"
    CALLS = "calls"
    MESSAGES = "messages"
    FILES = "files"

    SEND_MESSAGE = "send_message"
    MAKE_CALL = "make_call"


class PhonePermissionDenied(PermissionError):
    """Raised when an operation is attempted without its permission."""


READ_ONLY = {
    PhonePermision.Status,
    PhonePermision.NOTIFICATIONS,
    PhonePermision.CALLS,
    PhonePermision.MESSAGES,
    PhonePermision.FILES,
}

ACTION_PERMISSION = {
    PhonePermision.SEND_MESSAGE,
    PhonePermision.MAKE_CALL,
}

# Defaults follow least privilege - only the Phone Hub's core diagnostics
# and file sharing are granted out of the box:
#   granted  - status/devices/ping/encryption and file sharing, so the hub
#              stays usable without any policy configuration
#   withheld - notifications/messages: private device data must be granted
#              through an explicit policy, never enabled by default
#   withheld - send_message: a device-visible outgoing action must be
#              granted through an explicit policy, never enabled by default
#   withheld - calls/make-call: no KDE Connect call support anyway
DEFAULT_PERMISSIONS = {
    PhonePermision.Status: True,
    PhonePermision.CALLS: False,
    PhonePermision.NOTIFICATIONS: False,
    PhonePermision.MESSAGES: False,
    PhonePermision.FILES: True,
    PhonePermision.SEND_MESSAGE: False,
    PhonePermision.MAKE_CALL: False,
}


# Permission required by each Phone Hub command. Commands missing from this
# mapping are not gated (they never reach the device).
COMMAND_PERMISSIONS = {
    "status": PhonePermision.Status,
    "devices": PhonePermision.Status,
    "available": PhonePermision.Status,
    "refresh": PhonePermision.Status,
    "encryption": PhonePermision.Status,
    "ping": PhonePermision.Status,
    "permissions": PhonePermision.Status,
    "share": PhonePermision.FILES,
    "share-text": PhonePermision.FILES,
    "notifications": PhonePermision.NOTIFICATIONS,
    "messages": PhonePermision.MESSAGES,
    "list-sms": PhonePermision.MESSAGES,
    "sms": PhonePermision.SEND_MESSAGE,
}


def permission_label(permission: PhonePermision) -> str:
    labels = {
        PhonePermision.Status: "Status",
        PhonePermision.NOTIFICATIONS: "Notifications",
        PhonePermision.CALLS: "Calls",
        PhonePermision.MESSAGES: "Messages",
        PhonePermision.FILES: "Files",
        PhonePermision.SEND_MESSAGE: "Send Message",
        PhonePermision.MAKE_CALL: "Make Call",
    }

    return labels.get(permission, permission.value.replace("_", " ").title())


def is_allowed(
    permission: PhonePermision,
    permissions: dict[PhonePermision, bool] | None = None,
):
    state = DEFAULT_PERMISSIONS if permissions is None else permissions
    return bool(state.get(permission, False))


def require_permission(
    permission: PhonePermision,
    permissions: dict[PhonePermision, bool] | None = None,
) -> bool:
    """Enforce a permission grant.

    Raises PhonePermissionDenied when the permission is not granted. This is
    the enforcement point used by the Phone Hub - displaying a permission with
    a tick or a circle is never enough on its own.
    """
    if not is_allowed(permission, permissions):
        raise PhonePermissionDenied(
            f"Permission denied: '{permission_label(permission)}' is not granted."
        )
    return True


def command_permission(command: str | None) -> PhonePermision | None:
    """Return the permission a Phone Hub command requires (None = ungated)."""
    if not command:
        return None
    return COMMAND_PERMISSIONS.get(command)
