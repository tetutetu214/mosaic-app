"""shared.line_signature の単体テスト"""
import base64
import hashlib
import hmac

from shared.line_signature import verify_signature


def _make_signature(body: str, secret: str) -> str:
    """テスト用に正しい署名を生成するヘルパー"""
    return base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")


def test_verify_signature_valid():
    body = '{"events":[]}'
    secret = "test-secret"
    signature = _make_signature(body, secret)
    assert verify_signature(body, signature, secret) is True


def test_verify_signature_tampered_body():
    body = '{"events":[]}'
    secret = "test-secret"
    signature = _make_signature(body, secret)
    # ボディ改ざん時は False
    assert verify_signature('{"events":[1]}', signature, secret) is False


def test_verify_signature_wrong_secret():
    body = '{"events":[]}'
    signature = _make_signature(body, "test-secret")
    assert verify_signature(body, signature, "wrong-secret") is False


def test_verify_signature_empty_body_returns_false():
    assert verify_signature("", "any-signature", "any-secret") is False


def test_verify_signature_empty_signature_returns_false():
    assert verify_signature("body", "", "any-secret") is False


def test_verify_signature_empty_secret_returns_false():
    assert verify_signature("body", "any-signature", "") is False
