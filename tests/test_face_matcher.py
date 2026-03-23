"""
face_matcher.py のテスト（個別照合対応）
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from face_matcher import (
    filter_known_faces, 
    filter_known_faces_with_limit,
    filter_faces_individually
)


class TestFaceMatcher:
    """顔マッチャーのテスト"""
    
    def setup_method(self):
        """テスト用データ設定"""
        self.test_image = Image.new('RGB', (400, 300), color='white')
        self.detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_no_matches(self, mock_search):
        """マッチなしの場合のテスト"""
        mock_search.return_value = []
        
        result = filter_known_faces(self.detected_faces, 'bucket', 'key', 'collection')
        
        assert len(result) == 2  # 全ての顔が返される
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_with_high_similarity(self, mock_search):
        """高い類似度の場合のテスト"""
        mock_search.return_value = [{'Similarity': 95.0}]
        
        result = filter_known_faces(self.detected_faces, 'bucket', 'key', 'collection', similarity_threshold=70.0)
        
        assert len(result) == 1  # 1つの顔が除外される
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_with_low_similarity(self, mock_search):
        """低い類似度の場合のテスト"""
        mock_search.return_value = [{'Similarity': 50.0}]
        
        result = filter_known_faces(self.detected_faces, 'bucket', 'key', 'collection', similarity_threshold=70.0)
        
        assert len(result) == 2  # 全ての顔が返される
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_single_face(self, mock_search):
        """単一顔の場合のテスト"""
        mock_search.return_value = [{'Similarity': 95.0}]
        
        single_face = [self.detected_faces[0]]
        result = filter_known_faces(single_face, 'bucket', 'key', 'collection')
        
        assert len(result) == 0  # 唯一の顔が除外される
    
    def test_filter_known_faces_with_limit_too_many_faces(self):
        """顔数制限超過の場合のテスト"""
        many_faces = [
            {'BoundingBox': {'Left': 0.1 + i*0.1, 'Top': 0.1, 'Width': 0.05, 'Height': 0.05}}
            for i in range(7)  # 7人（制限5人を超過）
        ]
        
        result = filter_known_faces_with_limit(
            many_faces, self.test_image, 'bucket', 'prefix', 'collection', face_limit=5
        )
        
        assert len(result) == 7  # 全ての顔が返される（制限超過のため）
    
    @patch('face_matcher.filter_faces_individually')
    def test_filter_known_faces_with_limit_under_limit(self, mock_individual):
        """顔数制限内の場合のテスト"""
        mock_individual.return_value = [self.detected_faces[1]]  # 1つの顔を除外
        
        result = filter_known_faces_with_limit(
            self.detected_faces, self.test_image, 'bucket', 'prefix', 'collection', face_limit=5
        )
        
        assert len(result) == 1
        mock_individual.assert_called_once()
    
    @patch('image_handler.upload_to_s3')
    @patch('face_cropper.face_image_to_bytes')
    @patch('face_cropper.crop_all_faces')
    @patch('collection_manager.search_known_faces')
    def test_filter_faces_individually_user_found(self, mock_search, mock_crop, mock_to_bytes, mock_upload):
        """個別照合でユーザー発見の場合のテスト"""
        # モック設定
        mock_crop.return_value = [(Image.new('RGB', (100, 100)), 0), (Image.new('RGB', (100, 100)), 1)]
        mock_to_bytes.return_value = b'fake_image_data'
        
        # 最初の顔で高い類似度、2番目の顔で低い類似度
        mock_search.side_effect = [
            [{'Similarity': 95.0}],  # 1回目: 高い類似度
            [{'Similarity': 20.0}]   # 2回目: 低い類似度
        ]
        
        result = filter_faces_individually(
            self.detected_faces, self.test_image, 'bucket', 'prefix', 'collection', similarity_threshold=70.0
        )
        
        # 最初の顔（ユーザー）が除外され、2番目の顔のみ返される
        assert len(result) == 1
        assert result[0] == self.detected_faces[1]
    
    @patch('image_handler.upload_to_s3')
    @patch('face_cropper.face_image_to_bytes')
    @patch('face_cropper.crop_all_faces')
    @patch('collection_manager.search_known_faces')
    def test_filter_faces_individually_no_user(self, mock_search, mock_crop, mock_to_bytes, mock_upload):
        """個別照合でユーザー未発見の場合のテスト"""
        # モック設定
        mock_crop.return_value = [(Image.new('RGB', (100, 100)), 0), (Image.new('RGB', (100, 100)), 1)]
        mock_to_bytes.return_value = b'fake_image_data'
        
        # 両方とも低い類似度
        mock_search.side_effect = [
            [{'Similarity': 30.0}],  # 1回目: 低い類似度
            [{'Similarity': 25.0}]   # 2回目: 低い類似度
        ]
        
        result = filter_faces_individually(
            self.detected_faces, self.test_image, 'bucket', 'prefix', 'collection', similarity_threshold=70.0
        )
        
        # 全ての顔が返される
        assert len(result) == 2
        assert result == self.detected_faces
    
    @patch('image_handler.upload_to_s3')
    @patch('face_cropper.face_image_to_bytes')
    @patch('face_cropper.crop_all_faces')
    @patch('collection_manager.search_known_faces')
    def test_filter_faces_individually_multiple_registered_faces(self, mock_search, mock_crop, mock_to_bytes, mock_upload):
        """複数の登録済み顔がある場合、全て除外されるテスト"""
        three_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.4, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.7, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
        ]
        mock_crop.return_value = [
            (Image.new('RGB', (100, 100)), 0),
            (Image.new('RGB', (100, 100)), 1),
            (Image.new('RGB', (100, 100)), 2),
        ]
        mock_to_bytes.return_value = b'fake_image_data'

        # 1人目と2人目が登録済み、3人目は未登録
        mock_search.side_effect = [
            [{'Similarity': 95.0}],  # 1人目: 登録済み
            [{'Similarity': 90.0}],  # 2人目: 登録済み
            [{'Similarity': 20.0}],  # 3人目: 未登録
        ]

        result = filter_faces_individually(
            three_faces, self.test_image, 'bucket', 'prefix', 'collection', similarity_threshold=70.0
        )

        # 登録済みの2人が除外され、未登録の3人目のみモザイク対象
        assert len(result) == 1
        assert result[0] == three_faces[2]

    @patch('image_handler.upload_to_s3')
    @patch('face_matcher.face_image_to_bytes')
    @patch('face_matcher.crop_all_faces')
    @patch('collection_manager.search_known_faces')
    def test_filter_faces_individually_crop_failure(self, mock_search, mock_crop, mock_to_bytes, mock_upload):
        """顔クロップ失敗の場合のテスト"""
        # クロップが1つしか成功しない
        mock_crop.return_value = [(Image.new('RGB', (100, 100)), 0)]  # 1つの顔のみ
        mock_to_bytes.return_value = b'fake_image_data'
        mock_search.return_value = [{'Similarity': 95.0}]

        result = filter_faces_individually(
            self.detected_faces, self.test_image, 'bucket', 'prefix', 'collection', similarity_threshold=70.0
        )

        # クロップできた顔（インデックス0）が除外され、残りの顔が返される
        assert len(result) == 1
        assert result[0] == self.detected_faces[1]  # インデックス1の顔が残る
