"""
image_handler.py の統合テスト
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from image_handler import process_image_message


class TestImageHandlerIntegration:
    """画像処理ハンドラーの統合テスト"""
    
    @patch('image_handler.send_secure_image_reply')
    @patch('image_handler.apply_mosaic')
    @patch('image_handler.upload_to_s3')
    @patch('image_handler.download_image_from_line')
    @patch('image_handler.detect_faces')
    @patch('face_matcher.filter_known_faces')
    @patch('image_handler.search_known_faces')
    @patch('registration_state.is_registration_mode')
    def test_exclude_mode_with_known_faces(self, mock_registration, mock_search,
                                         mock_filter, mock_detect, mock_download, 
                                         mock_upload, mock_mosaic, mock_send):
        """excludeモードで登録済み顔が除外されることをテスト"""
        # モック設定
        mock_registration.return_value = False
        
        # 有効な画像データを作成
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        mock_download.return_value = img_buffer.getvalue()
        
        mock_detect.return_value = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
        mock_search.return_value = [{'Similarity': 85.0}]
        mock_filter.return_value = [mock_detect.return_value[1]]  # 1つの顔を除外
        mock_mosaic.return_value = img
        
        # 設定
        settings = {
            'mosaic_mode': 'exclude',
            's3_bucket_name': 'test-bucket',
            'rekognition_collection_id': 'test-collection',
            'line_channel_access_token': 'test-token'
        }
        
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user'}
        }
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証
        mock_filter.assert_called_once()
        mock_mosaic.assert_called_once()
        
        # モザイク関数に渡された顔の数をチェック
        mosaic_args = mock_mosaic.call_args[0]
        faces_to_mosaic = mosaic_args[1]
        
        assert len(faces_to_mosaic) == 1, "登録済み顔が除外されて1つの顔のみモザイク対象"
    
    @patch('image_handler.send_secure_image_reply')
    @patch('image_handler.apply_mosaic')
    @patch('image_handler.upload_to_s3')
    @patch('image_handler.download_image_from_line')
    @patch('image_handler.detect_faces')
    @patch('registration_state.is_registration_mode')
    def test_all_mode_processes_all_faces(self, mock_registration, mock_detect,
                                        mock_download, mock_upload, mock_mosaic, mock_send):
        """allモードで全ての顔が処理されることをテスト"""
        # モック設定
        mock_registration.return_value = False
        
        # 有効な画像データを作成
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        mock_download.return_value = img_buffer.getvalue()
        
        mock_detect.return_value = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
        mock_mosaic.return_value = img
        
        # 設定
        settings = {
            'mosaic_mode': 'all',
            's3_bucket_name': 'test-bucket',
            'rekognition_collection_id': 'test-collection',
            'line_channel_access_token': 'test-token'
        }
        
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user'}
        }
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証
        mock_mosaic.assert_called_once()
        
        # モザイク関数に渡された顔の数をチェック
        mosaic_args = mock_mosaic.call_args[0]
        faces_to_mosaic = mosaic_args[1]
        
        assert len(faces_to_mosaic) == 2, "allモードでは全ての顔がモザイク対象"

    @patch('image_handler.process_face_registration')
    @patch('registration_state.is_registration_mode')
    def test_registration_mode_calls_face_registration(self, mock_registration, mock_process_reg):
        """登録モード時に顔登録処理が呼ばれることをテスト"""
        # モック設定
        mock_registration.return_value = True
        
        # 設定
        settings = {
            'mosaic_mode': 'exclude',
            's3_bucket_name': 'test-bucket',
            'rekognition_collection_id': 'test-collection',
            'line_channel_access_token': 'test-token'
        }
        
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user'}
        }
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証
        mock_process_reg.assert_called_once_with(line_event, settings, 'test-user')
