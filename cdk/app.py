"""CDK アプリケーションエントリポイント"""
import aws_cdk as cdk

from stacks.mosaic_stack import MosaicStack

app = cdk.App()

MosaicStack(
    app, "MosaicAppV2",
    env=cdk.Environment(region="us-east-1"),
    s3_bucket_name=app.node.try_get_context("s3_bucket_name"),
    rekognition_collection_id=app.node.try_get_context(
        "rekognition_collection_id"
    ),
    line_channel_secret_param=app.node.try_get_context(
        "line_channel_secret_param"
    ),
    line_channel_access_token_param=app.node.try_get_context(
        "line_channel_access_token_param"
    ),
)

app.synth()
