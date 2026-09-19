# this program the isolation of sensitive information, so ai agent won't get all access, only restricted access

# class fot this to prevent error
class PhoneIsolationError(PermissionError):
    ...

def assert_phone_boundary(source: str):
    if source.strip().lower() in {
        "fox",
        "fox_agent",
        "agent",
        "ollama"
    }:
    raise PhoneIsolationError("Phone data is isolated from agent!")