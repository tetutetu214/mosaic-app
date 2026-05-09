"""署名検証パターンの単体テスト"""
import base64
import hashlib
import hmac
from unittest.mock import patch


def _make_signature(body: str, secret: str) -> str:
    return base64.b64encode(
        hmac.new(
            secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256,
        ).digest()
    ).decode("utf-8")


def _make_event(body: str, signature: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Line-Signature"] = signature
    return {
        "httpMethod": "POST",
        "headers": headers,
        "body": body,
        "isBase64Encoded": False,
    }


def test_invalid_signature_returns_403(app, aws_setup):
    body = '{"events":[]}'
    event = _make_event(body, "wrong-signature")

    with patch("shared.line_api.requests.post"):
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 403


def test_missing_signature_returns_403(app, aws_setup):
    body = '{"events":[]}'
    event = _make_event(body, signature=None)

    with patch("shared.line_api.requests.post"):
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 403


def test_empty_events_returns_200(app, aws_setup):
    body = '{"events":[]}'
    signature = _make_signature(body, aws_setup["channel_secret"])
    event = _make_event(body, signature)

    with patch("shared.line_api.requests.post"):
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200


def test_invalid_json_returns_400(app, aws_setup):
    body = "not-json-at-all"
    signature = _make_signature(body, aws_setup["channel_secret"])
    event = _make_event(body, signature)

    with patch("shared.line_api.requests.post"):
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 400


def test_lowercase_signature_header_is_accepted(app, aws_setup):
    """API Gateway がヘッダーを小文字化したケース"""
    body = '{"events":[]}'
    signature = _make_signature(body, aws_setup["channel_secret"])
    event = {
        "httpMethod": "POST",
        "headers": {
            "x-line-signature": signature,
            "content-type": "application/json",
        },
        "body": body,
        "isBase64Encoded": False,
    }

    with patch("shared.line_api.requests.post"):
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200
