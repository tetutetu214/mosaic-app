"""mosaic モード処理のテスト"""
from unittest.mock import patch

import boto3

from tests.processor.conftest import make_sqs_event


def _bbox(left=0.1, top=0.1, width=0.2, height=0.2) -> dict:
    return {
        "BoundingBox": {
            "Left": left, "Top": top, "Width": width, "Height": height,
        }
    }


def test_mosaic_normal_path(app, aws_setup, mock_line_api):
    event = make_sqs_event("mosaic", message_id="img-1")

    # 1顔検出、登録顔とマッチしない（=モザイク対象）
    with patch.object(app, "detect_faces", return_value=[_bbox()]), \
         patch.object(app, "filter_known_faces_with_limit", return_value=[_bbox()]):
        result = app.lambda_handler(event, None)

    assert result["batchItemFailures"] == []

    # S3 に input と output が存在
    s3 = boto3.client("s3", region_name="us-east-1")
    listed = s3.list_objects_v2(Bucket=aws_setup["bucket"]).get("Contents", [])
    keys = {obj["Key"] for obj in listed}
    assert "input/img-1.jpg" in keys
    assert "output/img-1.jpg" in keys

    # push_image が呼ばれた
    mock_line_api.push_image.assert_called_once()


def test_mosaic_no_faces_pushes_text(app, aws_setup, mock_line_api):
    event = make_sqs_event("mosaic", message_id="img-2")

    with patch.object(app, "detect_faces", return_value=[]):
        result = app.lambda_handler(event, None)

    assert result["batchItemFailures"] == []
    mock_line_api.push_text.assert_called_once()
    args, _ = mock_line_api.push_text.call_args
    assert "顔が検出されませんでした" in args[1]
    # push_image は呼ばれない
    mock_line_api.push_image.assert_not_called()


def test_mosaic_idempotent_with_same_message_id(app, aws_setup, mock_line_api):
    """同じ messageId で 2回処理しても S3 キーが同じ場所に上書きされる"""
    event = make_sqs_event("mosaic", message_id="img-dup")

    with patch.object(app, "detect_faces", return_value=[_bbox()]), \
         patch.object(app, "filter_known_faces_with_limit", return_value=[_bbox()]):
        app.lambda_handler(event, None)
        app.lambda_handler(event, None)

    s3 = boto3.client("s3", region_name="us-east-1")
    listed = s3.list_objects_v2(Bucket=aws_setup["bucket"]).get("Contents", [])
    keys = [obj["Key"] for obj in listed]
    # 重複キーが存在しない
    assert keys.count("input/img-dup.jpg") == 1
    assert keys.count("output/img-dup.jpg") == 1
