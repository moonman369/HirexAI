from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings


bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Paste JWT access token returned by /auth/login or /auth/signup",
)


def _password_bytes(password: str) -> bytes:
    # Pre-hash keeps bcrypt input short/consistent and avoids 72-byte limit failures.
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")
    return f"sha256_bcrypt${hashed}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        if password_hash.startswith("sha256_bcrypt$"):
            stored_hash = password_hash.split("$", 1)[1].encode("utf-8")
            return bcrypt.checkpw(_password_bytes(plain_password), stored_hash)

        # Backward compatibility with existing raw bcrypt hashes.
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, email: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_exp_minutes
    )
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    claims = decode_access_token(credentials.credentials)
    if "sub" not in claims:
        raise HTTPException(status_code=401, detail="Malformed token payload")
    return claims
