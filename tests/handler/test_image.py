"""画像メッセージ受信時のテスト（mosaic / register モード分岐）"""
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


def _make_event_with_image(
    secret: str,
    user_id: str = "U1234",
    message_id: str = "img-987",
) -> dict:
    body = json.dumps({
        "events": [
            {
                "type": "message",
                "message": {"type": "image", "id": message_id},
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


def _receive_one_message(queue_url: str) -> dict | None:
    sqs = boto3.client("sqs", region_name="us-east-1")
    resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    msgs = resp.get("Messages", [])
    return msgs[0] if msgs else None


def test_image_default_enqueues_mosaic_job(app, aws_setup):
    event = _make_event_with_image(aws_setup["channel_secret"])

    with patch("shared.line_api.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200

    # SQS に mode=mosaic でメッセージが入っているか
    msg = _receive_one_message(aws_setup["queue_url"])
    assert msg is not None
    body = json.loads(msg["Body"])
    assert body["mode"] == "mosaic"
    assert body["userId"] == "U1234"
    assert body["messageId"] == "img-987"


def test_image_in_register_mode_enqueues_register_job(app, aws_setup):
    # 事前に DynamoDB に登録モード ON を仕込む
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    table = ddb.Table(aws_setup["table_name"])
    table.put_item(Item={
        "userId": "U1234",
        "registrationMode": True,
        "ttl": 9999999999,
    })

    event = _make_event_with_image(aws_setup["channel_secret"])

    with patch("shared.line_api.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200

    # SQS に mode=register
    msg = _receive_one_message(aws_setup["queue_url"])
    assert msg is not None
    body = json.loads(msg["Body"])
    assert body["mode"] == "register"

    # 登録モードが OFF に戻されている
    item = table.get_item(Key={"userId": "U1234"}).get("Item")
    assert item is not None
    assert item["registrationMode"] is False


def test_sqs_send_failure_returns_200(app, aws_setup):
    """SQS 送信が失敗しても 200 を返す（LINE にリトライさせない）"""
    event = _make_event_with_image(aws_setup["channel_secret"])

    # sqs.send_message を例外を投げるようにモック
    with patch("shared.line_api.requests.post") as mock_post, \
         patch.object(app.sqs, "send_message", side_effect=RuntimeError("sqs down")):
        mock_post.return_value = MagicMock(status_code=200)
        result = app.lambda_handler(event, None)

    assert result["statusCode"] == 200
