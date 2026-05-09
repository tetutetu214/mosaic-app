"""register モード処理のテスト"""
from unittest.mock import patch

import boto3

from tests.processor.conftest import make_sqs_event


def _bbox() -> dict:
    return {
        "BoundingBox": {"Left": 0.1, "Top": 0.1, "Width": 0.2, "Height": 0.2}
    }


def test_register_normal_path(app, aws_setup, mock_line_api):
    """1顔 → IndexFaces → push_text"""
    event = make_sqs_event("register", message_id="reg-1", user_id="U1")

    with patch.object(app, "detect_faces", return_value=[_bbox()]), \
         patch.object(
             app, "add_face_to_collection", return_value="face-id-12345678"
         ) as mock_add:
        result = app.lambda_handler(event, None)

    assert result["batchItemFailures"] == []

    # IndexFaces に external_image_id=messageId が渡されている
    _, kwargs = mock_add.call_args
    assert kwargs.get("external_image_id") == "reg-1"

    # S3 に登録用キー
    s3 = boto3.client("s3", region_name="us-east-1")
    listed = s3.list_objects_v2(Bucket=aws_setup["bucket"]).get("Contents", [])
    keys = {obj["Key"] for obj in listed}
    assert "registration/U1/reg-1.jpg" in keys

    mock_line_api.push_text.assert_called_once()
    args, _ = mock_line_api.push_text.call_args
    assert "顔登録が完了しました" in args[1]


def test_register_no_faces_pushes_text(app, aws_setup, mock_line_api):
    event = make_sqs_event("register", message_id="reg-2")

    with patch.object(app, "detect_faces", return_value=[]):
        result = app.lambda_handler(event, None)

    assert result["batchItemFailures"] == []
    mock_line_api.push_text.assert_called_once()
    args, _ = mock_line_api.push_text.call_args
    assert "顔が検出されませんでした" in args[1]


def test_register_multiple_faces_pushes_text(app, aws_setup, mock_line_api):
    event = make_sqs_event("register", message_id="reg-3")

    with patch.object(app, "detect_faces", return_value=[_bbox(), _bbox()]):
        result = app.lambda_handler(event, None)

    assert result["batchItemFailures"] == []
    mock_line_api.push_text.assert_called_once()
    args, _ = mock_line_api.push_text.call_args
    assert "複数の顔" in args[1]
