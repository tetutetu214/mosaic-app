"""
mosaic_processor.py のテスト
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from mosaic_processor import apply_mosaic, detect_faces


class TestMosaicProcessor:
    """モザイク処理のテスト"""
    
    def test_apply_mosaic_basic(self):
        """基本的なモザイク処理テスト"""
        # 100x100のテスト画像作成
        test_image = Image.new('RGB', (100, 100), color='red')
        
        # 顔座標（BoundingBoxフォーマット）
        face_boxes = [{
            'BoundingBox': {
                'Left': 0.2,
                'Top': 0.3, 
                'Width': 0.4,
                'Height': 0.3
            }
        }]
        
        result = apply_mosaic(test_image, face_boxes)
        
        assert isinstance(result, Image.Image)
        assert result.size == (100, 100)
    
    @patch('boto3.client')
    def test_detect_faces(self, mock_boto_client):
        """顔検出APIのテスト"""
        # Rekognitionクライアントのモック
        mock_rekognition = Mock()
        mock_boto_client.return_value = mock_rekognition
        
        # レスポンスモック
        mock_rekognition.detect_faces.return_value = {
            'FaceDetails': [
                {
                    'BoundingBox': {
                        'Left': 0.1,
                        'Top': 0.2,
                        'Width': 0.3,
                        'Height': 0.4
                    }
                }
            ]
        }
        
        # テスト実行
        result = detect_faces('test-bucket', 'test-key')
        
        assert len(result) == 1
        assert 'BoundingBox' in result[0]
        mock_rekognition.detect_faces.assert_called_once()
