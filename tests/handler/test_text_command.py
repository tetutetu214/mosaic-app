"""テキストコマンド（登録 / 状態 / その他）のテスト"""
import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import boto3


def _make_signature(body: str, secret: str) -> str:
    return base64.b64encode(
        hmac.new(
            secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256,
        ).digest()
    ).decode("utf-8")


def _make_event_with_text(text: str, secret: str, user_id: str = "U1234") -> dict:
    body = json.dumps({
        "events": [
            {
                "type": "message",
                "message": {"type": "text", "text": text, "id": "msg-1"},
                "source": {"type": "user", "userId": user_id},
                "replyToken": "rt-1",
                "timestamp": 1234567890,
            }
        ]
    })
    signature = _make_signature(body, secret)
    return {
        "httpMethod": "POST",
        "headers": {
            "X-Line-Signature": signature,
            "Content-Type": "application/json",
        },
        "body": body,
        "isBase64Encoded": False,
    }


def test_text_register_sets_dynamodb_flag(app, aws_setup):
    event = _make_event_with_text("登録", aws_setup["channel_secret"])

    with patch("shared.line_api.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200

    # DynamoDB にフラグが立っていること
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    table = ddb.Table(aws_setup["table_name"])
    item = table.get_item(Key={"userId": "U1234"}).get("Item")
    assert item is not None
    assert item["registrationMode"] is True
    # TTL が今より未来であること
    assert item["ttl"] > 0


def test_text_status_returns_face_count(app, aws_setup):
    event = _make_event_with_text("状態", aws_setup["channel_secret"])

    with patch("shared.line_api.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200

    # reply 呼び出しの中身に「登録モード」「登録済み顔」が含まれる
    args, kwargs = mock_post.call_args
    reply_text = kwargs["json"]["messages"][0]["text"]
    assert "登録モード" in reply_text
    assert "登録済み顔" in reply_text


def test_text_unknown_does_nothing(app, aws_setup):
    event = _make_event_with_text("ふつうの会話", aws_setup["channel_secret"])

    with patch("shared.line_api.requests.post") as mock_post:
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200
    # reply API も呼ばれない
    mock_post.assert_not_called()

    # DynamoDB にも書き込まれない
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    table = ddb.Table(aws_setup["table_name"])
    item = table.get_item(Key={"userId": "U1234"}).get("Item")
    assert item is None
