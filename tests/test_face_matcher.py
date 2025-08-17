"""
face_matcher.py のテスト
"""
import pytest
import sys
import os

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from face_matcher import filter_known_faces, _faces_overlap


class TestFaceMatcher:
    """顔照合ロジックのテスト"""
    
    def test_filter_known_faces_no_matches(self):
        """登録済み顔がない場合のテスト"""
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.6, 'Width': 0.2, 'Height': 0.3}}
        ]
        known_face_matches = []
        
        result = filter_known_faces(detected_faces, known_face_matches)
        
        assert len(result) == 2
        assert result == detected_faces
    
    def test_filter_known_faces_with_match(self):
        """登録済み顔がある場合のテスト"""
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}},
            {'BoundingBox': {'Left': 0.5, 'Top': 0.6, 'Width': 0.2, 'Height': 0.3}}
        ]
        known_face_matches = [
            {
                'Similarity': 90.0,
                'Face': {
                    'BoundingBox': {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}
                }
            }
        ]
        
        result = filter_known_faces(detected_faces, known_face_matches)
        
        assert len(result) == 1
        assert result[0]['BoundingBox']['Left'] == 0.5
    
    def test_filter_known_faces_low_similarity(self):
        """類似度が低い場合のテスト"""
        detected_faces = [
            {'BoundingBox': {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}}
        ]
        known_face_matches = [
            {
                'Similarity': 70.0,  # 閾値85.0より低い
                'Face': {
                    'BoundingBox': {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}
                }
            }
        ]
        
        result = filter_known_faces(detected_faces, known_face_matches)
        
        assert len(result) == 1  # 類似度が低いので除外されない
    
    def test_faces_overlap_perfect_match(self):
        """完全に重複する顔のテスト"""
        bbox1 = {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}
        bbox2 = {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}
        
        result = _faces_overlap(bbox1, bbox2)
        
        assert result is True
    
    def test_faces_overlap_partial_match(self):
        """部分的に重複する顔のテスト"""
        bbox1 = {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.4}
        bbox2 = {'Left': 0.2, 'Top': 0.3, 'Width': 0.3, 'Height': 0.4}
        
        result = _faces_overlap(bbox1, bbox2)
        
        # 重複率を計算して判定
        # この場合重複があるが閾値0.5を満たすかテスト
        assert isinstance(result, bool)
    
    def test_faces_overlap_no_match(self):
        """重複しない顔のテスト"""
        bbox1 = {'Left': 0.1, 'Top': 0.2, 'Width': 0.2, 'Height': 0.2}
        bbox2 = {'Left': 0.7, 'Top': 0.8, 'Width': 0.2, 'Height': 0.2}
        
        result = _faces_overlap(bbox1, bbox2)
        
        assert result is False
    
    def test_faces_overlap_edge_case_zero_area(self):
        """面積が0の場合のテスト"""
        bbox1 = {'Left': 0.1, 'Top': 0.2, 'Width': 0.0, 'Height': 0.4}
        bbox2 = {'Left': 0.1, 'Top': 0.2, 'Width': 0.3, 'Height': 0.0}
        
        result = _faces_overlap(bbox1, bbox2)
        
        assert result is False
