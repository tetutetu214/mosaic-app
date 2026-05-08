"""部分バッチ失敗・リトライ通知のテスト"""
from unittest.mock import patch

from tests.processor.conftest import make_sqs_event


def test_failure_below_5_does_not_notify_user(app, aws_setup, mock_line_api):
    """receive_count < 5 では通知しない（リトライで成功する余地）"""
    event = make_sqs_event("mosaic", message_id="img-fail", receive_count=2)

    # detect_faces を例外にする
    with patch.object(app, "detect_faces", side_effect=RuntimeError("boom")):
        result = app.lambda_handler(event, None)

    # batchItemFailures に乗っている
    assert result["batchItemFailures"] == [{"itemIdentifier": "sqs-msg-1"}]

    # ユーザー通知は呼ばれていない
    mock_line_api.push_text.assert_not_called()


def test_failure_at_receive_count_5_notifies_user(app, aws_setup, mock_line_api):
    """receive_count == 5 で push_text 通知される"""
    event = make_sqs_event("mosaic", message_id="img-final", receive_count=5)

    with patch.object(app, "detect_faces", side_effect=RuntimeError("boom")):
        result = app.lambda_handler(event, None)

    assert result["batchItemFailures"] == [{"itemIdentifier": "sqs-msg-1"}]

    mock_line_api.push_text.assert_called_once()
    args, _ = mock_line_api.push_text.call_args
    assert "失敗" in args[1]


def test_unknown_mode_logs_and_does_not_fail(app, aws_setup, mock_line_api):
    """未知の mode は無視（DLQ送りにしない）"""
    event = make_sqs_event("nonsense")
    result = app.lambda_handler(event, None)

    # batchItemFailures に乗らない（成功扱い）
    assert result["batchItemFailures"] == []
