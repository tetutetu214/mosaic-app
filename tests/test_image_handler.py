"""
image_handler.py のテスト
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import json

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from image_handler import (
    generate_presigned_url,
    send_secure_image_reply,
    download_image_from_line,
    upload_to_s3,
    send_line_reply
)


class TestImageHandler:
    """画像処理ハンドラーのテスト"""
    
    @patch('boto3.client')
    def test_generate_presigned_url_success(self, mock_boto_client):
        """署名付きURL生成成功テスト"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        expected_url = "https://test-bucket.s3.amazonaws.com/test-key?signed=true"
        mock_s3.generate_presigned_url.return_value = expected_url
        
        result = generate_presigned_url('test-bucket', 'test-key', 3600)
        
        assert result == expected_url
        mock_s3.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': 'test-bucket', 'Key': 'test-key'},
            ExpiresIn=3600
        )
    
    @patch('boto3.client')
    def test_generate_presigned_url_failure(self, mock_boto_client):
        """署名付きURL生成失敗テスト"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        mock_s3.generate_presigned_url.side_effect = Exception("S3 error")
        
        with pytest.raises(Exception, match="S3 error"):
            generate_presigned_url('test-bucket', 'test-key')
    
    @patch('image_handler.requests.post')
    @patch('image_handler.generate_presigned_url')
    def test_send_secure_image_reply(self, mock_generate_url, mock_requests_post):
        """セキュア画像返信テスト"""
        mock_generate_url.return_value = "https://signed-url.com/image.jpg"
        mock_requests_post.return_value.status_code = 200
        
        settings = {
            'line_channel_access_token': 'test-token'
        }
        
        send_secure_image_reply('test-reply-token', 'test-bucket', 'test-key', settings)
        
        # 署名付きURL生成の確認
        mock_generate_url.assert_called_once_with('test-bucket', 'test-key', expiration=3600)
        
        # LINE APIコールの確認
        mock_requests_post.assert_called_once()
        call_args = mock_requests_post.call_args
        
        assert call_args[0][0] == 'https://api.line.me/v2/bot/message/reply'
        assert call_args[1]['headers']['Authorization'] == 'Bearer test-token'
        
        expected_data = {
            'replyToken': 'test-reply-token',
            'messages': [{
                'type': 'image',
                'originalContentUrl': 'https://signed-url.com/image.jpg',
                'previewImageUrl': 'https://signed-url.com/image.jpg'
            }]
        }
        assert call_args[1]['json'] == expected_data
    
    @patch('image_handler.requests.get')
    def test_download_image_from_line_success(self, mock_requests_get):
        """LINE画像ダウンロード成功テスト"""
        mock_response = Mock()
        mock_response.content = b'fake-image-data'
        mock_requests_get.return_value = mock_response
        
        settings = {
            'line_channel_access_token': 'test-token'
        }
        
        result = download_image_from_line('test-message-id', settings)
        
        assert result == b'fake-image-data'
        mock_requests_get.assert_called_once_with(
            'https://api-data.line.me/v2/bot/message/test-message-id/content',
            headers={'Authorization': 'Bearer test-token'}
        )
        mock_response.raise_for_status.assert_called_once()
    
    @patch('boto3.client')
    def test_upload_to_s3(self, mock_boto_client):
        """S3アップロードテスト"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        upload_to_s3(b'image-data', 'test-key', 'test-bucket')
        
        mock_s3.put_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test-key',
            Body=b'image-data',
            ContentType='image/jpeg'
        )
    
    @patch('image_handler.requests.post')
    def test_send_line_reply(self, mock_requests_post):
        """LINEテキスト返信テスト"""
        mock_requests_post.return_value.status_code = 200
        
        settings = {
            'line_channel_access_token': 'test-token'
        }
        
        send_line_reply('test-reply-token', 'テストメッセージ', settings)
        
        mock_requests_post.assert_called_once()
        call_args = mock_requests_post.call_args
        
        assert call_args[0][0] == 'https://api.line.me/v2/bot/message/reply'
        assert call_args[1]['headers']['Authorization'] == 'Bearer test-token'
        
        expected_data = {
            'replyToken': 'test-reply-token',
            'messages': [{
                'type': 'text',
                'text': 'テストメッセージ'
            }]
        }
        assert call_args[1]['json'] == expected_data
