"""
顔クロップ処理モジュール
"""
from PIL import Image
import io
from typing import List, Dict, Any, Tuple


def crop_face_from_image(image: Image.Image, face_detail: Dict[str, Any], padding: float = 0.2) -> Image.Image:
    """
    画像から指定された顔部分をクロップ
    
    Args:
        image: 元画像
        face_detail: 顔検出結果（BoundingBox含む）
        padding: 顔の周りに追加する余白（比率）
    
    Returns:
        クロップされた顔画像
    """
    bbox = face_detail['BoundingBox']
    width, height = image.size
    
    # 相対座標を絶対座標に変換
    left = int(bbox['Left'] * width)
    top = int(bbox['Top'] * height)
    face_width = int(bbox['Width'] * width)
    face_height = int(bbox['Height'] * height)
    
    # パディング追加
    padding_x = int(face_width * padding)
    padding_y = int(face_height * padding)
    
    # クロップ範囲計算（画像境界内に制限）
    crop_left = max(0, left - padding_x)
    crop_top = max(0, top - padding_y)
    crop_right = min(width, left + face_width + padding_x)
    crop_bottom = min(height, top + face_height + padding_y)
    
    # 最小サイズ確保（50x50ピクセル）
    min_size = 50
    if (crop_right - crop_left) < min_size or (crop_bottom - crop_top) < min_size:
        # 中心から最小サイズで切り出し
        center_x = left + face_width // 2
        center_y = top + face_height // 2
        half_size = min_size // 2
        
        crop_left = max(0, center_x - half_size)
        crop_top = max(0, center_y - half_size)
        crop_right = min(width, center_x + half_size)
        crop_bottom = min(height, center_y + half_size)
    
    return image.crop((crop_left, crop_top, crop_right, crop_bottom))


def crop_all_faces(image: Image.Image, face_details: List[Dict[str, Any]]) -> List[Tuple[Image.Image, int]]:
    """
    画像から全ての顔をクロップ
    
    Args:
        image: 元画像
        face_details: 顔検出結果のリスト
    
    Returns:
        [(クロップされた顔画像, 元の顔インデックス), ...]のリスト
    """
    cropped_faces = []
    
    for i, face_detail in enumerate(face_details):
        try:
            cropped_face = crop_face_from_image(image, face_detail)
            # 最小サイズチェック
            if cropped_face.size[0] >= 50 and cropped_face.size[1] >= 50:
                cropped_faces.append((cropped_face, i))
        except Exception as e:
            print(f"Failed to crop face {i}: {str(e)}")
            continue
    
    return cropped_faces


def face_image_to_bytes(face_image: Image.Image, format: str = 'JPEG') -> bytes:
    """
    顔画像をバイト列に変換
    
    Args:
        face_image: 顔画像
        format: 出力フォーマット
    
    Returns:
        画像のバイト列
    """
    buffer = io.BytesIO()
    face_image.save(buffer, format=format)
    return buffer.getvalue()


def calculate_face_size(face_detail: Dict[str, Any]) -> float:
    """
    顔のサイズ（面積）を計算
    
    Args:
        face_detail: 顔検出結果
    
    Returns:
        顔の面積（相対値）
    """
    bbox = face_detail['BoundingBox']
    return bbox['Width'] * bbox['Height']
