# Centralized authentication for the Brain HTTP API.
#
# Every protected route uses this single dependency - no route performs its
# own token check. The token lives only in the FOX_API_TOKEN environment
# variable and is never hardcoded, logged, or returned in responses.
#
# Fail-closed behaviour:
#   - missing/empty FOX_API_TOKEN on the server -> everything protected 401s
#   - missing/invalid X-API-Token header      -> 401, no information leaked
# /health endpoints stay public on purpose (liveness only, no data, no writes).

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader


API_TOKEN_ENV_VAR = "FOX_API_TOKEN"
API_TOKEN_HEADER = "X-API-Token"


_api_key_header = APIKeyHeader(name=API_TOKEN_HEADER, auto_error=False)


def get_configured_token() -> str | None:
    """Return the server-side token, or None when it is not configured."""
    token = os.environ.get(API_TOKEN_ENV_VAR)
    return token if token else None


def require_api_token(provided: str | None = Depends(_api_key_header)) -> None:
    """FastAPI dependency guarding every mutating/task route.

    Raises HTTP 401 for a missing server token, a missing client header,
    or a mismatched token. Comparison is constant-time.
    """
    configured = get_configured_token()
    if (
        not configured
        or not provided
        or not secrets.compare_digest(provided, configured)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token.",
        )
