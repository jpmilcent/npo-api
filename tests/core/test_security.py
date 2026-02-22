from datetime import timedelta

import jwt
import pytest

import npo.core.security
from npo.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_verify_password():
    plain_password = "password123"
    # Generate hash with: echo -n "password123"| argon2 $(uuid) -id -m 16 -p 4
    hashed_password = (
        "$argon2id$v=19$m=65536,t=3,p=4"
        "$MDNkZGQyNjctMGY0Mi0xMWYxLWFmZTEtMzBlM2E0NWUyY"
        "mU0$rinEZomGjwzHq9BtrgV5nMb4OY2tm4ZZ5Ebp6LYfKpw"
    )

    assert verify_password(plain_password, hashed_password) is True
    assert verify_password("wrong_password", hashed_password) is False


def test_get_password_hash():
    plain_password = "password123"
    hashed_password = get_password_hash(plain_password)
    assert verify_password(plain_password, hashed_password)


def test_create_access_token():
    data = {"sub": "test@example.com"}
    token = create_access_token(data)
    decoded = decode_access_token(token)
    assert decoded["sub"] == data["sub"]
    assert "exp" in decoded
    assert "iat" in decoded
    assert "jti" in decoded
    # Un access token ne devrait pas avoir le type "refresh" par défaut
    assert "type" not in decoded


def test_create_refresh_token():
    data = {"sub": "test@example.com"}
    token = create_refresh_token(data)
    # On décode manuellement pour vérifier le champ 'type'
    decoded = jwt.decode(token, npo.core.security.SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == data["sub"]
    assert decoded["type"] == "refresh"
    assert "exp" in decoded
    assert "iat" in decoded
    assert "jti" in decoded


def test_token_expiration():
    data = {"sub": "test@example.com"}
    # Créer un token qui a expiré il y a 1 seconde
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_invalid_token():
    with pytest.raises(jwt.DecodeError):
        decode_access_token("invalid.token.value")
