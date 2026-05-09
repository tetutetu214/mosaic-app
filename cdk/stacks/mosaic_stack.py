"""mosaic-app v2 メインスタック定義"""
from pathlib import Path
from typing import Any

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as event_sources,
    aws_sqs as sqs,
)
from constructs import Construct

# cdk/stacks/mosaic_stack.py から見たプロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent

# DockerImageAsset の build context から除外するパス
# - PROJECT_ROOT を context にすると CDK が asset を cdk/cdk.out にコピーする際、
#   cdk/cdk.out/ 自身が含まれて無限ネストする ENAMETOOLONG エラーになる
# - .venv は数百MBあって不要、tests/docs/lambda-function も Lambda 実行時に不要
DOCKER_ASSET_EXCLUDES: list[str] = [
    "cdk/cdk.out",
    "cdk/.cdk.staging",
    "cdk",
    ".venv",
    "tests",
    "docs",
    "lambda-function",
    "scripts",
    ".git",
    "node_modules",
    "**/__pycache__",
    ".pytest_cache",
    "*.zip",
    "*.md",
]


class MosaicStack(Stack):
    """LINE webhook → SQS → 画像処理の非同期スタック"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        s3_bucket_name: str | None,
        rekognition_collection_id: str | None,
        line_channel_secret_param: str | None,
        line_channel_access_token_param: str | None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # context バリデーション（未指定なら明確に落とす）
        if not s3_bucket_name:
            raise ValueError("context 's3_bucket_name' is required")
        if not rekognition_collection_id:
            raise ValueError("context 'rekognition_collection_id' is required")
        if not line_channel_secret_param:
            raise ValueError("context 'line_channel_secret_param' is required")
        if not line_channel_access_token_param:
            raise ValueError(
                "context 'line_channel_access_token_param' is required"
            )

        account_id = Stack.of(self).account
        region = Stack.of(self).region

        # 1. DLQ（保管期限14日、SQSマネージド暗号化）
        dlq = sqs.Queue(
            self, "ProcessorDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # 2. メインキュー（visibility は関数 timeout の6倍）
        queue = sqs.Queue(
            self, "ProcessorQueue",
            visibility_timeout=Duration.seconds(1080),
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5, queue=dlq,
            ),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # 9. 登録モード状態管理テーブル
        table = dynamodb.Table(
            self, "RegistrationStateTable",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 3. handler Lambda
        handler_fn = _lambda.DockerImageFunction(
            self, "HandlerFunction",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=str(PROJECT_ROOT),
                file="handler/Dockerfile",
                exclude=DOCKER_ASSET_EXCLUDES,
            ),
            timeout=Duration.seconds(5),
            memory_size=512,  # コールドスタート対策(CPU配分増加でInit短縮)
            environment={
                "SQS_QUEUE_URL": queue.queue_url,
                "REGISTRATION_TABLE_NAME": table.table_name,
                "REKOGNITION_COLLECTION_ID": rekognition_collection_id,
                "LINE_CHANNEL_SECRET_PARAM": line_channel_secret_param,
                "LINE_CHANNEL_ACCESS_TOKEN_PARAM":
                    line_channel_access_token_param,
            },
        )
        queue.grant_send_messages(handler_fn)
        table.grant_read_write_data(handler_fn)
        handler_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{region}:{account_id}:parameter"
                    f"{line_channel_secret_param}",
                    f"arn:aws:ssm:{region}:{account_id}:parameter"
                    f"{line_channel_access_token_param}",
                ],
            )
        )
        handler_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rekognition:ListFaces"],
                resources=[
                    f"arn:aws:rekognition:{region}:{account_id}:collection/"
                    f"{rekognition_collection_id}",
                ],
            )
        )

        # 4. processor Lambda
        processor_fn = _lambda.DockerImageFunction(
            self, "ProcessorFunction",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=str(PROJECT_ROOT),
                file="processor/Dockerfile",
                exclude=DOCKER_ASSET_EXCLUDES,
            ),
            timeout=Duration.seconds(180),
            memory_size=1024,
            reserved_concurrent_executions=5,
            environment={
                "S3_BUCKET_NAME": s3_bucket_name,
                "REKOGNITION_COLLECTION_ID": rekognition_collection_id,
                "MOSAIC_MODE": "exclude",
                "LINE_CHANNEL_ACCESS_TOKEN_PARAM":
                    line_channel_access_token_param,
            },
        )
        queue.grant_consume_messages(processor_fn)
        processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:PutObject"],
                resources=[f"arn:aws:s3:::{s3_bucket_name}/*"],
            )
        )
        # rekognition:DetectFaces はコレクション非依存のため Resource: "*"
        processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rekognition:DetectFaces"],
                resources=["*"],
            )
        )
        # IndexFaces / SearchFacesByImage はコレクションに紐付く
        processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "rekognition:IndexFaces",
                    "rekognition:SearchFacesByImage",
                ],
                resources=[
                    f"arn:aws:rekognition:{region}:{account_id}:collection/"
                    f"{rekognition_collection_id}",
                ],
            )
        )
        processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{region}:{account_id}:parameter"
                    f"{line_channel_access_token_param}",
                ],
            )
        )

        # 5. SQS → processor のイベントソース
        processor_fn.add_event_source(
            event_sources.SqsEventSource(
                queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )

        # 6-8. API Gateway
        api = apigw.RestApi(
            self, "MosaicApi",
            rest_api_name="mosaic-app-v2-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )
        webhook = api.root.add_resource("webhook")
        webhook.add_method("POST", apigw.LambdaIntegration(handler_fn))
