"""
text_handler.py のテスト
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from text_handler import process_text_message, get_registered_face_count


class TestTextHandler:
    """テキストメッセージハンドラーのテスト"""
    
    @patch('text_handler.send_registration_instruction')
    def test_process_text_message_register(self, mock_send_instruction):
        """「登録」メッセージのテスト"""
        line_event = {
            'message': {'text': '登録'},
            'replyToken': 'test-reply-token'
        }
        settings = {'test': 'settings'}
        
        process_text_message(line_event, settings)
        
        mock_send_instruction.assert_called_once_with('test-reply-token', settings)
    
    @patch('text_handler.send_status_info')
    def test_process_text_message_status(self, mock_send_status):
        """「状態」メッセージのテスト"""
        line_event = {
            'message': {'text': '状態'},
            'replyToken': 'test-reply-token'
        }
        settings = {'test': 'settings'}
        
        process_text_message(line_event, settings)
        
        mock_send_status.assert_called_once_with('test-reply-token', settings)
    
    def test_process_text_message_unknown(self):
        """不明なメッセージのテスト"""
        line_event = {
            'message': {'text': '不明なコマンド'},
            'replyToken': 'test-reply-token'
        }
        settings = {'test': 'settings'}
        
        # 例外が発生しないことを確認
        process_text_message(line_event, settings)
    
    @patch('boto3.client')
    def test_get_registered_face_count_success(self, mock_boto_client):
        """登録済み顔数取得成功テスト"""
        mock_rekognition = Mock()
        mock_boto_client.return_value = mock_rekognition
        
        mock_rekognition.list_faces.return_value = {
            'Faces': [{'FaceId': 'face1'}, {'FaceId': 'face2'}]
        }
        
        result = get_registered_face_count('test-collection')
        
        assert result == 2
    
    @patch('boto3.client')
    def test_get_registered_face_count_not_found(self, mock_boto_client):
        """コレクション未作成時のテスト"""
        mock_rekognition = Mock()
        mock_boto_client.return_value = mock_rekognition
        
        # ClientErrorを使用してResourceNotFoundExceptionを模擬
        error_response = {'Error': {'Code': 'ResourceNotFoundException'}}
        mock_rekognition.list_faces.side_effect = ClientError(error_response, 'ListFaces')
        
        result = get_registered_face_count('test-collection')
        
        assert result == 0
