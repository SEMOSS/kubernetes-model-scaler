from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
import os

VALID_API_KEYS = os.getenv("VALID_API_KEYS", "").split(",")
API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not VALID_API_KEYS or VALID_API_KEYS == [""]:
        raise HTTPException(status_code=500, detail="API key configuration error")

    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
