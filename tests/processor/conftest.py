"""tests/processor 共通フィクスチャ"""
import importlib
import os
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws
from PIL import Image

# Lambda LAMBDA_TASK_ROOT 相当のパスを sys.path に追加して
# processor/ 内部の `from mosaic_processor import ...` などを解決可能にする
PROCESSOR_DIR = Path(__file__).parent.parent.parent / "processor"
if str(PROCESSOR_DIR) not in sys.path:
    sys.path.insert(0, str(PROCESSOR_DIR))

S3_BUCKET = "test-bucket"
COLLECTION_ID = "test-collection"
TOKEN_PARAM = "/test/line-channel-access-token"
CHANNEL_TOKEN = "test-token"


def make_test_image_bytes(size: tuple[int, int] = (100, 100)) -> bytes:
    """テスト用に小さな白色 JPEG を生成する"""
    img = Image.new("RGB", size, color="white")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def aws_setup():
    """moto で S3 / SSM をセットアップし、環境変数を仕込む"""
    with mock_aws():
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=S3_BUCKET)

        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(
            Name=TOKEN_PARAM, Value=CHANNEL_TOKEN, Type="SecureString",
        )

        os.environ["S3_BUCKET_NAME"] = S3_BUCKET
        os.environ["REKOGNITION_COLLECTION_ID"] = COLLECTION_ID
        os.environ["MOSAIC_MODE"] = "exclude"
        os.environ["LINE_CHANNEL_ACCESS_TOKEN_PARAM"] = TOKEN_PARAM

        yield {
            "bucket": S3_BUCKET,
            "collection_id": COLLECTION_ID,
            "token_param": TOKEN_PARAM,
        }


@pytest.fixture
def app(aws_setup):
    """環境変数セットアップ後に processor.app をフレッシュインポート"""
    sys.modules.pop("processor.app", None)
    sys.modules.pop("processor", None)
    import processor.app as processor_app
    importlib.reload(processor_app)
    processor_app._token_cache.clear()
    return processor_app


@pytest.fixture
def mock_line_api(monkeypatch):
    """LineApiClient をまるごと差し替えるフィクスチャ"""
    instance = MagicMock()
    instance.download_content.return_value = make_test_image_bytes()

    def factory(_token: str):
        return instance

    monkeypatch.setattr("processor.app.LineApiClient", factory)
    return instance


def make_sqs_event(
    mode: str,
    user_id: str = "U1234",
    message_id: str = "img-987",
    receive_count: int = 1,
    sqs_msg_id: str = "sqs-msg-1",
    timestamp: int = 1234567890,
) -> dict:
    """SQS イベント風の dict を作る"""
    import json
    return {
        "Records": [
            {
                "messageId": sqs_msg_id,
                "body": json.dumps({
                    "mode": mode,
                    "userId": user_id,
                    "messageId": message_id,
                    "timestamp": timestamp,
                }),
                "attributes": {
                    "ApproximateReceiveCount": str(receive_count),
                },
            }
        ]
    }
