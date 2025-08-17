"""
image_handler.py の統合テスト（個別照合対応）
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import json
import io
from PIL import Image

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from image_handler import process_image_message


class TestImageHandlerIntegration:
    """画像処理の統合テスト"""
    
    @patch('image_handler.send_secure_image_reply')
    @patch('image_handler.upload_to_s3')
    @patch('image_handler.download_image_from_line')
    @patch('image_handler.apply_mosaic')
    @patch('image_handler.detect_faces')
    @patch('face_matcher.filter_known_faces_with_limit')
    @patch('registration_state.is_registration_mode')
    def test_exclude_mode_under_limit(self, mock_registration_mode, mock_filter_limit,
                                    mock_detect_faces, mock_apply_mosaic,
                                    mock_download, mock_upload, mock_send_reply):
        """excludeモードで顔数制限内の場合のテスト"""
        # 登録モードではない
        mock_registration_mode.return_value = False
        
        # 画像データのモック
        test_image = Image.new('RGB', (100, 100), color='red')
        image_buffer = io.BytesIO()
        test_image.save(image_buffer, format='JPEG')
        mock_download.return_value = image_buffer.getvalue()
        
        # 3人の顔を検出（制限内）
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.4, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.7, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}}
        ]
        mock_detect_faces.return_value = detected_faces
        
        # ユーザーの顔を除外（2人にモザイク）
        mock_filter_limit.return_value = detected_faces[1:]
        
        # モザイク処理の結果
        mock_apply_mosaic.return_value = test_image
        
        # テスト用イベント
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user-id'}
        }
        
        settings = {
            'mosaic_mode': 'exclude',
            's3_bucket_name': 'test-bucket',
            'rekognition_collection_id': 'test-collection',
            'line_channel_access_token': 'test-token'
        }
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証
        mock_filter_limit.assert_called_once()
        # filter_known_faces_with_limitの引数確認
        args, kwargs = mock_filter_limit.call_args
        assert args[0] == detected_faces  # detected_faces
        assert args[2] == 'test-bucket'   # bucket
        assert args[4] == 'test-collection'  # collection_id
        
        mock_apply_mosaic.assert_called_once()
        mock_send_reply.assert_called_once()
    
    @patch('image_handler.send_secure_image_reply')
    @patch('image_handler.upload_to_s3')
    @patch('image_handler.download_image_from_line')
    @patch('image_handler.apply_mosaic')
    @patch('image_handler.detect_faces')
    @patch('face_matcher.filter_known_faces_with_limit')
    @patch('registration_state.is_registration_mode')
    def test_exclude_mode_over_limit(self, mock_registration_mode, mock_filter_limit,
                                   mock_detect_faces, mock_apply_mosaic,
                                   mock_download, mock_upload, mock_send_reply):
        """excludeモードで顔数制限超過の場合のテスト"""
        # 登録モードではない
        mock_registration_mode.return_value = False
        
        # 画像データのモック
        test_image = Image.new('RGB', (100, 100), color='red')
        image_buffer = io.BytesIO()
        test_image.save(image_buffer, format='JPEG')
        mock_download.return_value = image_buffer.getvalue()
        
        # 6人の顔を検出（制限超過）
        detected_faces = [
            {'BoundingBox': {'Left': 0.1 + i*0.15, 'Top': 0.1, 'Width': 0.1, 'Height': 0.1}}
            for i in range(6)
        ]
        mock_detect_faces.return_value = detected_faces
        
        # 制限超過で全員にモザイク
        mock_filter_limit.return_value = detected_faces
        
        # モザイク処理の結果
        mock_apply_mosaic.return_value = test_image
        
        # テスト用イベント
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user-id'}
        }
        
        settings = {
            'mosaic_mode': 'exclude',
            's3_bucket_name': 'test-bucket',
            'rekognition_collection_id': 'test-collection',
            'line_channel_access_token': 'test-token'
        }
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証
        mock_filter_limit.assert_called_once()
        # 全ての顔にモザイクが適用される（画像オブジェクトの型は無視）
        mock_apply_mosaic.assert_called_once()
        args, kwargs = mock_apply_mosaic.call_args
        # 第2引数（faces）が正しいかチェック
        assert args[1] == detected_faces
        mock_send_reply.assert_called_once()
    
    @patch('image_handler.send_secure_image_reply')
    @patch('image_handler.upload_to_s3')
    @patch('image_handler.download_image_from_line')
    @patch('image_handler.apply_mosaic')
    @patch('image_handler.detect_faces')
    @patch('registration_state.is_registration_mode')
    def test_all_mode_processes_all_faces(self, mock_registration_mode, mock_detect_faces, 
                                        mock_apply_mosaic, mock_download, mock_upload, mock_send_reply):
        """allモードで全ての顔を処理するテスト"""
        # 登録モードではない
        mock_registration_mode.return_value = False
        
        # 画像データのモック
        test_image = Image.new('RGB', (100, 100), color='red')
        image_buffer = io.BytesIO()
        test_image.save(image_buffer, format='JPEG')
        mock_download.return_value = image_buffer.getvalue()
        
        # 顔検出の結果
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
        mock_detect_faces.return_value = detected_faces
        
        # モザイク処理の結果
        mock_apply_mosaic.return_value = test_image
        
        # テスト用イベント
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user-id'}
        }
        
        settings = {
            'mosaic_mode': 'all',
            's3_bucket_name': 'test-bucket',
            'line_channel_access_token': 'test-token'
        }
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証: allモードでは個別照合は使われない
        args, kwargs = mock_apply_mosaic.call_args
        assert args[1] == detected_faces  # 全ての顔がモザイク対象
        mock_send_reply.assert_called_once()
    
    @patch('image_handler.process_face_registration')
    @patch('registration_state.is_registration_mode')
    def test_registration_mode_calls_face_registration(self, mock_registration_mode, mock_face_registration):
        """登録モードの場合、顔登録処理が呼ばれるテスト"""
        # 登録モード
        mock_registration_mode.return_value = True
        
        # テスト用イベント
        line_event = {
            'message': {'id': 'test-message-id'},
            'replyToken': 'test-reply-token',
            'source': {'userId': 'test-user-id'}
        }
        
        settings = {'test': 'settings'}
        
        # テスト実行
        process_image_message(line_event, settings)
        
        # 検証
        mock_face_registration.assert_called_once_with(line_event, settings, 'test-user-id')
