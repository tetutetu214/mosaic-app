"""
face_cropper.py のテスト
"""
import pytest
import sys
import os
from PIL import Image
import io

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from face_cropper import (
    crop_face_from_image,
    crop_all_faces,
    face_image_to_bytes,
    calculate_face_size
)


class TestFaceCropper:
    """顔クロップ処理のテスト"""
    
    def setup_method(self):
        """テスト用画像作成"""
        self.test_image = Image.new('RGB', (400, 300), color='white')
        
        # テスト用顔検出データ
        self.face_detail = {
            'BoundingBox': {
                'Left': 0.1,
                'Top': 0.2,
                'Width': 0.3,
                'Height': 0.4
            }
        }
    
    def test_crop_face_from_image_basic(self):
        """基本的な顔クロップテスト"""
        cropped = crop_face_from_image(self.test_image, self.face_detail)
        
        assert isinstance(cropped, Image.Image)
        assert cropped.size[0] > 0 and cropped.size[1] > 0
    
    def test_crop_face_from_image_with_padding(self):
        """パディング付き顔クロップテスト"""
        cropped = crop_face_from_image(self.test_image, self.face_detail, padding=0.5)
        
        # パディングありの方が大きくなることを確認
        cropped_no_padding = crop_face_from_image(self.test_image, self.face_detail, padding=0.0)
        
        assert cropped.size[0] >= cropped_no_padding.size[0]
        assert cropped.size[1] >= cropped_no_padding.size[1]
    
    def test_crop_face_boundary_protection(self):
        """画像境界保護テスト"""
        # 画像端の顔
        edge_face = {
            'BoundingBox': {
                'Left': 0.9,
                'Top': 0.9,
                'Width': 0.1,
                'Height': 0.1
            }
        }
        
        cropped = crop_face_from_image(self.test_image, edge_face, padding=0.5)
        
        # エラーなく処理されることを確認
        assert isinstance(cropped, Image.Image)
        assert cropped.size[0] > 0 and cropped.size[1] > 0
    
    def test_crop_face_minimum_size(self):
        """最小サイズ保証テスト"""
        # 非常に小さい顔
        tiny_face = {
            'BoundingBox': {
                'Left': 0.4,
                'Top': 0.4,
                'Width': 0.01,
                'Height': 0.01
            }
        }
        
        cropped = crop_face_from_image(self.test_image, tiny_face)
        
        # 最小サイズ50x50が保証されることを確認
        assert cropped.size[0] >= 50
        assert cropped.size[1] >= 50
    
    def test_crop_all_faces(self):
        """全顔クロップテスト"""
        face_details = [
            {
                'BoundingBox': {
                    'Left': 0.1,
                    'Top': 0.1,
                    'Width': 0.2,
                    'Height': 0.2
                }
            },
            {
                'BoundingBox': {
                    'Left': 0.6,
                    'Top': 0.6,
                    'Width': 0.2,
                    'Height': 0.2
                }
            }
        ]
        
        cropped_faces = crop_all_faces(self.test_image, face_details)
        
        assert len(cropped_faces) == 2
        
        for cropped_face, index in cropped_faces:
            assert isinstance(cropped_face, Image.Image)
            assert isinstance(index, int)
            assert 0 <= index < len(face_details)
    
    def test_crop_all_faces_with_invalid_face(self):
        """無効な顔を含む全顔クロップテスト"""
        face_details = [
            {
                'BoundingBox': {
                    'Left': 0.1,
                    'Top': 0.1,
                    'Width': 0.2,
                    'Height': 0.2
                }
            },
            {
                'BoundingBox': {
                    'Left': 1.5,  # 無効な座標
                    'Top': 1.5,
                    'Width': 0.2,
                    'Height': 0.2
                }
            }
        ]
        
        cropped_faces = crop_all_faces(self.test_image, face_details)
        
        # 有効な顔のみ処理されることを確認
        assert len(cropped_faces) == 1
        assert cropped_faces[0][1] == 0  # 最初の顔のインデックス
    
    def test_face_image_to_bytes(self):
        """顔画像バイト変換テスト"""
        test_face = Image.new('RGB', (100, 100), color='red')
        
        image_bytes = face_image_to_bytes(test_face)
        
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0
        
        # バイト列から画像を復元できることを確認
        restored_image = Image.open(io.BytesIO(image_bytes))
        assert restored_image.size == (100, 100)
    
    def test_face_image_to_bytes_png(self):
        """PNG形式での顔画像バイト変換テスト"""
        test_face = Image.new('RGB', (100, 100), color='blue')
        
        image_bytes = face_image_to_bytes(test_face, format='PNG')
        
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0
    
    def test_calculate_face_size(self):
        """顔サイズ計算テスト"""
        face_detail = {
            'BoundingBox': {
                'Left': 0.1,
                'Top': 0.2,
                'Width': 0.3,
                'Height': 0.4
            }
        }
        
        size = calculate_face_size(face_detail)
        
        assert size == 0.3 * 0.4  # Width * Height
        assert size == 0.12
    
    def test_calculate_face_size_comparison(self):
        """顔サイズ比較テスト（浮動小数点精度対応）"""
        large_face = {
            'BoundingBox': {
                'Left': 0.1,
                'Top': 0.1,
                'Width': 0.5,
                'Height': 0.6
            }
        }
        
        small_face = {
            'BoundingBox': {
                'Left': 0.7,
                'Top': 0.7,
                'Width': 0.1,
                'Height': 0.1
            }
        }
        
        large_size = calculate_face_size(large_face)
        small_size = calculate_face_size(small_face)
        
        assert large_size > small_size
        assert large_size == 0.3  # 0.5 * 0.6
        # 浮動小数点精度を考慮
        assert abs(small_size - 0.01) < 1e-10  # 0.1 * 0.1
