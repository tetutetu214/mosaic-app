"""tests/handler 共通フィクスチャ"""
import importlib
import os
import sys

import boto3
import pytest
from moto import mock_aws

CHANNEL_SECRET = "test-channel-secret"
CHANNEL_TOKEN = "test-channel-access-token"
SECRET_PARAM = "/test/line-channel-secret"
TOKEN_PARAM = "/test/line-channel-access-token"
TABLE_NAME = "test-registration-table"
COLLECTION_ID = "test-collection"


@pytest.fixture
def aws_setup():
    """moto で DynamoDB / SQS / SSM をセットアップし、環境変数を仕込む"""
    with mock_aws():
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        ddb = boto3.client("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="test-queue")["QueueUrl"]

        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(
            Name=SECRET_PARAM, Value=CHANNEL_SECRET, Type="SecureString",
        )
        ssm.put_parameter(
            Name=TOKEN_PARAM, Value=CHANNEL_TOKEN, Type="SecureString",
        )

        os.environ["SQS_QUEUE_URL"] = queue_url
        os.environ["REGISTRATION_TABLE_NAME"] = TABLE_NAME
        os.environ["REKOGNITION_COLLECTION_ID"] = COLLECTION_ID
        os.environ["LINE_CHANNEL_SECRET_PARAM"] = SECRET_PARAM
        os.environ["LINE_CHANNEL_ACCESS_TOKEN_PARAM"] = TOKEN_PARAM

        yield {
            "queue_url": queue_url,
            "table_name": TABLE_NAME,
            "channel_secret": CHANNEL_SECRET,
            "channel_token": CHANNEL_TOKEN,
            "secret_param": SECRET_PARAM,
            "token_param": TOKEN_PARAM,
        }


@pytest.fixture
def app(aws_setup):
    """環境変数セットアップ後に handler.app をフレッシュインポートする"""
    # 既存の import を捨てて、moto モック下で再評価させる
    sys.modules.pop("handler.app", None)
    sys.modules.pop("handler", None)
    import handler.app as handler_app
    importlib.reload(handler_app)
    handler_app._line_secret_cache.clear()
    return handler_app
