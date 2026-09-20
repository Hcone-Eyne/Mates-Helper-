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

DEFAULT_PERMISSIONS = {
    PhonePermision.Status: True,
    PhonePermision.CALLS: False,
    PhonePermision.NOTIFICATIONS: False,
    PhonePermision.MESSAGES: False,
    PhonePermision.FILES: True,
    PhonePermision.SEND_MESSAGE: False,
    PhonePermision.MAKE_CALL: False,
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
    state = permissions or DEFAULT_PERMISSIONS
    return bool(state.get(permission, False))