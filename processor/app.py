"""画像処理 Lambda（SQS 駆動）"""
import json
import logging
import os
from io import BytesIO
from typing import Any

import boto3
from PIL import Image

from shared.line_api import LineApiClient

# 既存ロジックの移植先（同ディレクトリの兄弟モジュール）
from mosaic_processor import detect_faces, apply_mosaic
from face_matcher import filter_known_faces_with_limit
from collection_manager import add_face_to_collection

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

S3_BUCKET = os.environ["S3_BUCKET_NAME"]
COLLECTION_ID = os.environ["REKOGNITION_COLLECTION_ID"]
MOSAIC_MODE = os.environ["MOSAIC_MODE"]
LINE_TOKEN_PARAM = os.environ["LINE_CHANNEL_ACCESS_TOKEN_PARAM"]

PRESIGNED_URL_TTL = 3600
FACE_LIMIT = 20
SIMILARITY_THRESHOLD = 50.0
MAX_RECEIVE_COUNT_FOR_NOTIFY = 5

s3 = boto3.client("s3")
ssm = boto3.client("ssm")
_token_cache: dict[str, str] = {}


def _get_token() -> str:
    if "token" not in _token_cache:
        resp = ssm.get_parameter(Name=LINE_TOKEN_PARAM, WithDecryption=True)
        _token_cache["token"] = resp["Parameter"]["Value"]
    return _token_cache["token"]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    line_api = LineApiClient(_get_token())
    failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        sqs_msg_id = record["messageId"]
        receive_count = int(
            record.get("attributes", {}).get("ApproximateReceiveCount", "1")
        )
        msg = json.loads(record["body"])

        try:
            if msg["mode"] == "mosaic":
                _process_mosaic(msg, line_api)
            elif msg["mode"] == "register":
                _process_register(msg, line_api)
            else:
                LOGGER.error("unknown mode: %s", msg.get("mode"))
        except Exception:
            LOGGER.exception(
                "processing failed: line_message_id=%s receive_count=%s",
                msg.get("messageId"), receive_count,
            )
            # 最終試行（DLQ送り直前）のみユーザーに通知
            if receive_count >= MAX_RECEIVE_COUNT_FOR_NOTIFY:
                _safely_notify_failure(line_api, msg.get("userId"))
            failures.append({"itemIdentifier": sqs_msg_id})

    return {"batchItemFailures": failures}


def _process_mosaic(msg: dict, line_api: LineApiClient) -> None:
    user_id = msg["userId"]
    line_message_id = msg["messageId"]

    # 1. LINE から画像取得
    image_data = line_api.download_content(line_message_id)

    # 2. S3 アップロード（messageId ベースで冪等）
    input_key = f"input/{line_message_id}.jpg"
    s3.put_object(
        Bucket=S3_BUCKET, Key=input_key, Body=image_data,
        ContentType="image/jpeg",
    )

    # 3. 顔検出
    faces = detect_faces(S3_BUCKET, input_key)
    if not faces:
        line_api.push_text(user_id, "顔が検出されませんでした。")
        return

    # 4. モザイク対象決定
    if MOSAIC_MODE == "exclude":
        original_image = Image.open(BytesIO(image_data))
        faces_to_mosaic = filter_known_faces_with_limit(
            faces, original_image, S3_BUCKET,
            f"faces/{line_message_id}", COLLECTION_ID,
            s3_client=s3,
            face_limit=FACE_LIMIT,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )
    else:
        faces_to_mosaic = faces

    # 5. モザイク適用
    image = Image.open(BytesIO(image_data))
    mosaic_image = apply_mosaic(image, faces_to_mosaic)

    # 6. 出力アップロード
    output_key = f"output/{line_message_id}.jpg"
    output_buffer = BytesIO()
    mosaic_image.save(output_buffer, format="JPEG")
    s3.put_object(
        Bucket=S3_BUCKET, Key=output_key,
        Body=output_buffer.getvalue(), ContentType="image/jpeg",
    )

    # 7. presigned URL → Push API
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": output_key},
        ExpiresIn=PRESIGNED_URL_TTL,
    )
    line_api.push_image(user_id, presigned_url, presigned_url)


def _process_register(msg: dict, line_api: LineApiClient) -> None:
    user_id = msg["userId"]
    line_message_id = msg["messageId"]

    image_data = line_api.download_content(line_message_id)

    image_key = f"registration/{user_id}/{line_message_id}.jpg"
    s3.put_object(
        Bucket=S3_BUCKET, Key=image_key, Body=image_data,
        ContentType="image/jpeg",
    )

    faces = detect_faces(S3_BUCKET, image_key)
    if not faces:
        line_api.push_text(
            user_id,
            "顔が検出されませんでした。別の画像で再度お試しください。",
        )
        return
    if len(faces) > 1:
        line_api.push_text(
            user_id,
            "複数の顔が検出されました。1人だけが写った画像を送信してください。",
        )
        return

    face_id = add_face_to_collection(
        S3_BUCKET, image_key, COLLECTION_ID,
        external_image_id=line_message_id,
    )
    line_api.push_text(
        user_id, f"顔登録が完了しました。\n登録ID: {face_id[:8]}...",
    )


def _safely_notify_failure(
    line_api: LineApiClient, user_id: str | None,
) -> None:
    """DLQ 送り直前のみ呼ばれる。Push 失敗で例外を投げない。"""
    if not user_id:
        return
    try:
        line_api.push_text(
            user_id,
            "画像処理に失敗しました。お手数ですがもう一度送信してください。",
        )
    except Exception:
        LOGGER.exception("failure notification push failed")
