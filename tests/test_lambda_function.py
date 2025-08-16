"""
lambda_function.py のテスト
"""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from lambda_function import lambda_handler


class TestLambdaHandler:
    """Lambda関数のテスト"""
    
    @patch.dict(os.environ, {
        'AWS_REGION': 'us-east-1',
        'S3_BUCKET_NAME': 'test-bucket',
        'REKOGNITION_COLLECTION_ID': 'test-collection',
        'MOSAIC_MODE': 'all',
        'LINE_CHANNEL_ACCESS_TOKEN': 'test-token',
        'LINE_CHANNEL_SECRET': 'test-secret'
    })
    def test_lambda_handler_basic(self):
        """基本的な動作テスト"""
        event = {}
        context = {}
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        assert 'body' in response
    
    @patch.dict(os.environ, {
        'AWS_REGION': 'us-east-1',
        'S3_BUCKET_NAME': 'test-bucket',
        'REKOGNITION_COLLECTION_ID': 'test-collection',
        'MOSAIC_MODE': 'all',
        'LINE_CHANNEL_ACCESS_TOKEN': 'test-token',
        'LINE_CHANNEL_SECRET': 'test-secret'
    })
    @patch('lambda_function.process_line_webhook')
    def test_line_webhook_event(self, mock_process):
        """LINE Webhook イベントの処理テスト"""
        event = {
            'body': json.dumps({
                'events': [{
                    'type': 'message',
                    'message': {
                        'type': 'image',
                        'id': 'test-message-id'
                    },
                    'replyToken': 'test-reply-token'
                }]
            }),
            'headers': {
                'x-line-signature': 'test-signature'
            }
        }
        context = {}
        
        mock_process.return_value = {'statusCode': 200}
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        mock_process.assert_called_once()
