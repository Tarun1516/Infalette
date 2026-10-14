"""Unit tests for auth: password hashing and JWT."""

import pytest
from uuid import uuid4
from datetime import timedelta

from infalette_auth.security import PasswordHasher
from infalette_auth.jwt import TokenManager


def test_password_hasher_hash_and_verify():
    hasher = PasswordHasher(rounds=4)  # low rounds for speed
    pwd = "SuperSecret123!"
    hashed = hasher.hash_password(pwd)
    assert hashed != pwd
    assert hasher.verify_password(pwd, hashed) is True
    assert hasher.verify_password("wrong", hashed) is False
    # Invalid hash should not raise, just return False
    assert hasher.verify_password(pwd, "not-a-valid-hash") is False


def test_password_hasher_recovery_codes():
    hasher = PasswordHasher(rounds=4)
    codes = hasher.generate_recovery_codes(count=5)
    assert len(codes) == 5
    assert len(set(codes)) == 5  # unique


def test_token_manager_create_and_decode():
    mgr = TokenManager()
    tenant_id = uuid4()
    user_id = str(uuid4())
    token = mgr.create_access_token(subject=user_id, tenant_id=tenant_id)
    assert isinstance(token, str)
    assert token.count(".") == 2  # JWT
    payload = mgr.decode_token(token)
    assert payload.sub == user_id
    assert payload.tenant_id == str(tenant_id)
    assert payload.token_type == "access"
    assert mgr.verify_token(token) is True


def test_token_manager_refresh_token():
    mgr = TokenManager()
    tenant_id = uuid4()
    user_id = str(uuid4())
    refresh = mgr.create_refresh_token(subject=user_id, tenant_id=tenant_id)
    payload = mgr.decode_token(refresh)
    assert payload.token_type == "refresh"
    assert mgr.verify_token(refresh) is True


def test_token_manager_expiry_and_invalid():
    mgr = TokenManager()
    tenant_id = uuid4()
    user_id = str(uuid4())
    # Expired token
    token = mgr.create_access_token(subject=user_id, tenant_id=tenant_id, expires_delta=timedelta(seconds=-1))
    assert mgr.verify_token(token) is False
    # Invalid token
    assert mgr.verify_token("invalid.token.here") is False
    with pytest.raises(Exception):
        mgr.decode_token("not-a-token")


def test_password_hasher_different_hashes():
    hasher = PasswordHasher(rounds=4)
    pwd = "same-password"
    h1 = hasher.hash_password(pwd)
    h2 = hasher.hash_password(pwd)
    assert h1 != h2  # different salts
    assert hasher.verify_password(pwd, h1) is True
    assert hasher.verify_password(pwd, h2) is True
