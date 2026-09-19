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
    PhonePermision.STATUS, 
    PhonePermision.NOTIFICATIONS,
    PhonePermision.CALLS,
    PhonePermision.MESSAGES,
    PhonePermision.FILES
}

ACTION_PERMISSION = {
    PhonePermision.SEND_MESSAGE,
    PhonePermision.MAKE_CALL
}