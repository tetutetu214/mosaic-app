"""
collection_manager.py のテスト
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from collection_manager import search_known_faces, add_face_to_collection


class TestCollectionManager:
    """顔コレクション管理のテスト"""
    
    @patch('boto3.client')
    def test_search_known_faces_found(self, mock_boto_client):
        """登録済み顔の検索テスト（発見）"""
        # Rekognitionクライアントのモック
        mock_rekognition = Mock()
        mock_boto_client.return_value = mock_rekognition
        
        # レスポンスモック
        mock_rekognition.search_faces_by_image.return_value = {
            'FaceMatches': [
                {
                    'Face': {
                        'FaceId': 'test-face-id',
                        'Confidence': 99.5
                    },
                    'Similarity': 95.0
                }
            ]
        }
        
        result = search_known_faces('test-bucket', 'test-key', 'test-collection')
        
        assert isinstance(result, list)
        assert len(result) == 1
        mock_rekognition.search_faces_by_image.assert_called_once()
    
    @patch('boto3.client')
    def test_add_face_to_collection(self, mock_boto_client):
        """顔をコレクションに追加するテスト"""
        mock_rekognition = Mock()
        mock_boto_client.return_value = mock_rekognition
        
        # レスポンスモック
        mock_rekognition.index_faces.return_value = {
            'FaceRecords': [
                {
                    'Face': {
                        'FaceId': 'new-face-id'
                    }
                }
            ]
        }
        
        face_id = add_face_to_collection('test-bucket', 'test-key', 'test-collection')
        
        assert face_id == 'new-face-id'
        mock_rekognition.index_faces.assert_called_once()
