"""Auth0 JWT validation for FastAPI endpoints."""

import jwt
import httpx
import logging
from functools import lru_cache

from fastapi import HTTPException, Request

from config import settings

logger = logging.getLogger(__name__)

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    """Fetch and cache the Auth0 JWKS (JSON Web Key Set)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _find_rsa_key(jwks: dict, kid: str) -> dict | None:
    """Find the RSA key matching the given kid in the JWKS."""
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
    return None


async def _decode_token(token: str) -> dict:
    """Validate and decode an Auth0 JWT access token."""
    if not settings.auth0_domain or not settings.auth0_audience:
        raise HTTPException(
            status_code=500,
            detail="Auth0 is not configured on the server.",
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token header.")

    jwks = await _get_jwks()
    rsa_key = _find_rsa_key(jwks, unverified_header.get("kid", ""))

    if rsa_key is None:
        # Key may have rotated — clear cache and retry once
        global _jwks_cache
        _jwks_cache = None
        jwks = await _get_jwks()
        rsa_key = _find_rsa_key(jwks, unverified_header.get("kid", ""))
        if rsa_key is None:
            raise HTTPException(status_code=401, detail="Unable to find signing key.")

    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(rsa_key)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Invalid token audience.")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid token issuer.")
    except jwt.PyJWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token.")


def _extract_bearer_token(request: Request) -> str | None:
    """Extract the Bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(request: Request) -> str:
    """FastAPI dependency: validate JWT and return the Auth0 user ID (sub claim)."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    payload = await _decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub claim.")
    return sub


async def get_optional_user(request: Request) -> str | None:
    """Like get_current_user but returns None for unauthenticated requests."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    try:
        payload = await _decode_token(token)
        return payload.get("sub")
    except HTTPException:
        return None
