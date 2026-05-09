"""LINE webhook 受信 Lambda（軽量・即200返却）"""
import json
import logging
import os
import time
from typing import Any

import boto3

from shared.line_api import LineApiClient
from shared.line_signature import verify_signature

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
REGISTRATION_TABLE_NAME = os.environ["REGISTRATION_TABLE_NAME"]
REKOGNITION_COLLECTION_ID = os.environ["REKOGNITION_COLLECTION_ID"]
LINE_CHANNEL_SECRET_PARAM = os.environ["LINE_CHANNEL_SECRET_PARAM"]
LINE_CHANNEL_ACCESS_TOKEN_PARAM = os.environ["LINE_CHANNEL_ACCESS_TOKEN_PARAM"]

TTL_SECONDS = 24 * 60 * 60

# モジュールレベルでクライアント初期化（コールドスタート時のみ走る）
sqs = boto3.client("sqs")
ddb = boto3.resource("dynamodb")
ssm = boto3.client("ssm")
rekognition = boto3.client("rekognition")
table = ddb.Table(REGISTRATION_TABLE_NAME)

# シークレットはコールドスタート時に取得してキャッシュ
_line_secret_cache: dict[str, str] = {}


def _get_secret(param_name: str) -> str:
    if param_name not in _line_secret_cache:
        resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
        _line_secret_cache[param_name] = resp["Parameter"]["Value"]
    return _line_secret_cache[param_name]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    body_str = event.get("body") or ""
    # API Gateway や CloudFront で大文字小文字が変わるため両方を吸収する
    headers = event.get("headers") or {}
    headers_lower = {k.lower(): v for k, v in headers.items()}
    signature = headers_lower.get("x-line-signature", "")

    # 署名検証
    channel_secret = _get_secret(LINE_CHANNEL_SECRET_PARAM)
    if not verify_signature(body_str, signature, channel_secret):
        LOGGER.warning(
            "invalid signature (body_len=%d signature_present=%s)",
            len(body_str), bool(signature),
        )
        return _response(403, {"error": "invalid signature"})

    # JSON パース
    try:
        webhook = json.loads(body_str)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid json"})

    line_api = LineApiClient(_get_secret(LINE_CHANNEL_ACCESS_TOKEN_PARAM))

    # events ループ
    for ev in webhook.get("events", []):
        try:
            _handle_event(ev, line_api)
        except Exception as e:
            # 個別イベント失敗で全体を落とさない
            LOGGER.exception("event handling failed: %s", e)

    return _response(200, {"status": "ok"})


def _handle_event(ev: dict[str, Any], line_api: LineApiClient) -> None:
    if ev.get("type") != "message":
        return  # follow / unfollow / postback 等は無視

    message = ev.get("message", {})
    user_id = ev.get("source", {}).get("userId")
    reply_token = ev.get("replyToken", "")
    if not user_id:
        return  # group / room など想定外のソースは無視

    msg_type = message.get("type")
    if msg_type == "text":
        _handle_text(user_id, message["text"], reply_token, line_api)
    elif msg_type == "image":
        _handle_image(
            user_id, message["id"], reply_token, ev["timestamp"], line_api,
        )


def _handle_text(
    user_id: str, text: str, reply_token: str, line_api: LineApiClient,
) -> None:
    text = text.strip()
    if text == "登録":
        table.put_item(Item={
            "userId": user_id,
            "registrationMode": True,
            "ttl": int(time.time()) + TTL_SECONDS,
        })
        line_api.reply(
            reply_token,
            "顔登録モードを開始しました。\n次に1人だけ写った画像を1枚送ってください。",
        )
    elif text == "状態":
        item = table.get_item(Key={"userId": user_id}).get("Item")
        in_mode = bool(item and item.get("registrationMode"))
        face_count = _count_registered_faces()
        line_api.reply(
            reply_token,
            f"登録モード: {'ON' if in_mode else 'OFF'}\n登録済み顔: {face_count}個",
        )
    # それ以外のテキストは無視


def _handle_image(
    user_id: str,
    message_id: str,
    reply_token: str,
    timestamp: int,
    line_api: LineApiClient,
) -> None:
    # 登録モード確認
    item = table.get_item(Key={"userId": user_id}).get("Item")
    in_mode = bool(item and item.get("registrationMode"))
    mode = "register" if in_mode else "mosaic"

    # SQS にエンキュー
    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps({
            "mode": mode,
            "userId": user_id,
            "messageId": message_id,
            "timestamp": timestamp,
        }),
    )

    # 登録モードを OFF に戻す（連続登録を防ぐ）
    if in_mode:
        table.put_item(Item={
            "userId": user_id,
            "registrationMode": False,
            "ttl": int(time.time()) + TTL_SECONDS,
        })

    # ユーザーへ即時状況返信
    msg = "顔を登録しています…" if in_mode else "モザイク処理中です…"
    line_api.reply(reply_token, msg)


def _count_registered_faces() -> int:
    try:
        resp = rekognition.list_faces(CollectionId=REKOGNITION_COLLECTION_ID)
        return len(resp.get("Faces", []))
    except Exception:
        # 取得失敗時は -1 を返して呼び出し側に "不明" と表示させる
        return -1


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "body": json.dumps(body)}
