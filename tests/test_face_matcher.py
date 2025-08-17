"""
face_matcher.py のテスト
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from face_matcher import filter_known_faces


class TestFaceMatcher:
    """顔照合モジュールのテスト"""
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_no_matches(self, mock_search):
        """登録済み顔が見つからない場合のテスト"""
        mock_search.return_value = []
        
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
        
        result = filter_known_faces(detected_faces, 'bucket', 'key', 'collection')
        
        assert len(result) == 2
        assert result == detected_faces
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_with_high_similarity(self, mock_search):
        """高い類似度の登録済み顔が見つかった場合のテスト"""
        mock_search.return_value = [{'Similarity': 85.0}]
        
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
        
        result = filter_known_faces(detected_faces, 'bucket', 'key', 'collection')
        
        assert len(result) == 1
        assert result == [detected_faces[1]]
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_with_low_similarity(self, mock_search):
        """低い類似度の場合のテスト"""
        mock_search.return_value = [{'Similarity': 50.0}]
        
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.5, 'Width': 0.2, 'Height': 0.2}}
        ]
        
        result = filter_known_faces(detected_faces, 'bucket', 'key', 'collection', similarity_threshold=70.0)
        
        assert len(result) == 2
        assert result == detected_faces
    
    @patch('collection_manager.search_known_faces')
    def test_filter_known_faces_single_face(self, mock_search):
        """検出顔が1つの場合のテスト"""
        mock_search.return_value = [{'Similarity': 85.0}]
        
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.1, 'Width': 0.2, 'Height': 0.2}}
        ]
        
        result = filter_known_faces(detected_faces, 'bucket', 'key', 'collection')
        
        assert len(result) == 0
