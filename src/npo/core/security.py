import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from npo.core.config import backend_settings

SECRET_KEY: str = backend_settings.jwt_secret_key
ALGORITHM: str = backend_settings.jwt_algorithm

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(
    data: dict, expires_delta: timedelta | None = None, sid: str | None = None
) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + expires_delta if expires_delta else now + timedelta(minutes=15)
    # Ajout de 'iat' et d'un 'jti' unique pour garantir que le token est différent à chaque appel
    to_encode.update({"exp": expire, "iat": now, "jti": str(uuid.uuid4())})
    if sid:
        to_encode["sid"] = sid
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + expires_delta if expires_delta else now + timedelta(days=7)
    to_encode.update({"exp": expire, "iat": now, "jti": str(uuid.uuid4()), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload
