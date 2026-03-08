"""
JARVIS — Unit Tests: Auth Service (no DB required)
Tests password hashing, JWT encoding/decoding in isolation.
"""
import pytest
import os

# Set dummy env vars before importing backend
os.environ.setdefault("GROQ_API_KEY",  "test_key")
os.environ.setdefault("DATABASE_URL",  "postgresql://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET",    "test_secret_minimum_32_chars_long_here")

from backend.services.auth_service import hash_password, verify_password, issue_token, decode_token


class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        h = hash_password("mypassword123")
        assert h != "mypassword123"
        assert h.startswith("$2b$")

    def test_verify_correct_password(self):
        h = hash_password("correct_password")
        assert verify_password("correct_password", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correct_password")
        assert verify_password("wrong_password", h) is False

    def test_verify_empty_fails(self):
        h = hash_password("somepassword")
        assert verify_password("", h) is False

    def test_hash_is_unique(self):
        # Same password should produce different hashes (different salts)
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2
        # But both should verify
        assert verify_password("samepassword", h1)
        assert verify_password("samepassword", h2)

    def test_bcrypt_cost_factor(self):
        # $2b$12$ means cost factor 12
        h = hash_password("test")
        assert "$2b$12$" in h


class TestJWT:
    def test_issue_and_decode(self):
        token = issue_token("lucky", "dev_123")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "lucky"
        assert payload["did"] == "dev_123"

    def test_invalid_token_returns_none(self):
        result = decode_token("invalid.token.here")
        assert result is None

    def test_empty_token_returns_none(self):
        result = decode_token("")
        assert result is None

    def test_token_has_expiry(self):
        token = issue_token("lucky")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_token_has_jti(self):
        """Each token has unique ID (prevents replay)."""
        t1 = issue_token("lucky")
        t2 = issue_token("lucky")
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]
