"""shared.line_api の単体テスト"""
from unittest.mock import MagicMock, patch

import pytest

from shared.line_api import LineApiClient


@patch("shared.line_api.requests.post")
def test_reply_calls_reply_endpoint_with_correct_payload(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    client = LineApiClient("fake-token")

    client.reply("reply-token-123", "hello")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.line.me/v2/bot/message/reply"
    assert kwargs["json"] == {
        "replyToken": "reply-token-123",
        "messages": [{"type": "text", "text": "hello"}],
    }
    assert kwargs["headers"]["Authorization"] == "Bearer fake-token"


@patch("shared.line_api.requests.post")
def test_push_text_calls_push_endpoint_with_correct_payload(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    client = LineApiClient("fake-token")

    client.push_text("U1234", "hello")

    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.line.me/v2/bot/message/push"
    assert kwargs["json"] == {
        "to": "U1234",
        "messages": [{"type": "text", "text": "hello"}],
    }


@patch("shared.line_api.requests.post")
def test_push_image_includes_both_urls(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    client = LineApiClient("fake-token")

    client.push_image(
        "U1234",
        "https://example.com/orig.jpg",
        "https://example.com/prev.jpg",
    )

    args, kwargs = mock_post.call_args
    assert kwargs["json"]["messages"] == [
        {
            "type": "image",
            "originalContentUrl": "https://example.com/orig.jpg",
            "previewImageUrl": "https://example.com/prev.jpg",
        }
    ]


@patch("shared.line_api.requests.get")
def test_download_content_returns_response_bytes(mock_get):
    mock_get.return_value = MagicMock(status_code=200, content=b"image-bytes")
    client = LineApiClient("fake-token")

    result = client.download_content("msg-123")

    assert result == b"image-bytes"
    args, kwargs = mock_get.call_args
    assert "msg-123" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer fake-token"


@patch("shared.line_api.requests.post")
def test_reply_raises_on_http_error(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("boom")
    mock_post.return_value = mock_response
    client = LineApiClient("fake-token")

    with pytest.raises(Exception, match="boom"):
        client.reply("rt", "hello")
