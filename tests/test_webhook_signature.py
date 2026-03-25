"""Tests for Linear webhook HMAC-SHA256 signature verification."""

import hashlib
import hmac

from shared.linear_client import verify_webhook


def _make_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_valid_signature() -> None:
    body = b'{"action":"update","type":"Issue"}'
    secret = "test-secret-123"
    signature = _make_signature(body, secret)
    assert verify_webhook(body, signature, secret) is True


def test_invalid_signature() -> None:
    body = b'{"action":"update","type":"Issue"}'
    secret = "test-secret-123"
    assert verify_webhook(body, "invalid-signature", secret) is False


def test_wrong_secret() -> None:
    body = b'{"action":"update","type":"Issue"}'
    secret = "test-secret-123"
    wrong_secret = "wrong-secret"
    signature = _make_signature(body, wrong_secret)
    assert verify_webhook(body, signature, secret) is False


def test_empty_body() -> None:
    body = b""
    secret = "test-secret-123"
    signature = _make_signature(body, secret)
    assert verify_webhook(body, signature, secret) is True


def test_unicode_body() -> None:
    body = '{"title":"測試議題"}'.encode("utf-8")
    secret = "test-secret-123"
    signature = _make_signature(body, secret)
    assert verify_webhook(body, signature, secret) is True
