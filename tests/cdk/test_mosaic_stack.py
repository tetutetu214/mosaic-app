"""MosaicStack のスナップショットテスト"""
import sys
from pathlib import Path

# cdk/ ディレクトリを sys.path に追加して stacks.mosaic_stack を import 可能にする
CDK_DIR = Path(__file__).parent.parent.parent / "cdk"
if str(CDK_DIR) not in sys.path:
    sys.path.insert(0, str(CDK_DIR))

from aws_cdk import App  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from stacks.mosaic_stack import MosaicStack  # noqa: E402


def _make_template() -> Template:
    """テスト用にスタックをインスタンス化し、CFn テンプレートを返す"""
    app = App()
    stack = MosaicStack(
        app, "TestStack",
        env={"region": "us-east-1", "account": "123456789012"},
        s3_bucket_name="test-bucket",
        rekognition_collection_id="test-collection",
        line_channel_secret_param="/test/line-channel-secret",
        line_channel_access_token_param="/test/line-channel-access-token",
    )
    return Template.from_stack(stack)


def test_resource_counts():
    template = _make_template()
    template.resource_count_is("AWS::Lambda::Function", 2)
    template.resource_count_is("AWS::SQS::Queue", 2)
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.resource_count_is("AWS::Lambda::EventSourceMapping", 1)


def test_processor_queue_visibility_timeout():
    template = _make_template()
    template.has_resource_properties(
        "AWS::SQS::Queue",
        Match.object_like({"VisibilityTimeout": 1080}),
    )


def test_dlq_max_receive_count_5():
    template = _make_template()
    template.has_resource_properties(
        "AWS::SQS::Queue",
        Match.object_like({
            "RedrivePolicy": Match.object_like({"maxReceiveCount": 5}),
        }),
    )


def test_event_source_batch_size_and_partial_response():
    template = _make_template()
    template.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        Match.object_like({
            "BatchSize": 1,
            "FunctionResponseTypes": ["ReportBatchItemFailures"],
        }),
    )


def test_processor_function_settings():
    template = _make_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        Match.object_like({
            "Timeout": 180,
            "MemorySize": 1024,
            "ReservedConcurrentExecutions": 5,
        }),
    )


def test_handler_function_settings():
    template = _make_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        Match.object_like({
            "Timeout": 5,
            "MemorySize": 256,
        }),
    )


def test_dynamodb_pay_per_request_with_ttl():
    template = _make_template()
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        Match.object_like({
            "BillingMode": "PAY_PER_REQUEST",
            "TimeToLiveSpecification": Match.object_like({
                "AttributeName": "ttl",
                "Enabled": True,
            }),
        }),
    )


def test_api_gateway_method_post_webhook():
    template = _make_template()
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        Match.object_like({"HttpMethod": "POST"}),
    )


def test_missing_context_raises():
    """context 未指定時に ValueError"""
    import pytest
    app = App()
    with pytest.raises(ValueError, match="s3_bucket_name"):
        MosaicStack(
            app, "MissingContextStack",
            env={"region": "us-east-1", "account": "123456789012"},
            s3_bucket_name=None,
            rekognition_collection_id="x",
            line_channel_secret_param="/x",
            line_channel_access_token_param="/y",
        )
