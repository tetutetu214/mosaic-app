"""顔クロップ処理モジュール"""
import io
from typing import Any

from PIL import Image


def crop_face_from_image(
    image: Image.Image,
    face_detail: dict[str, Any],
    padding: float = 0.2,
) -> Image.Image:
    """画像から指定された顔部分をクロップ（パディング付き）"""
    bbox = face_detail["BoundingBox"]
    width, height = image.size

    left = int(bbox["Left"] * width)
    top = int(bbox["Top"] * height)
    face_width = int(bbox["Width"] * width)
    face_height = int(bbox["Height"] * height)

    padding_x = int(face_width * padding)
    padding_y = int(face_height * padding)

    crop_left = max(0, left - padding_x)
    crop_top = max(0, top - padding_y)
    crop_right = min(width, left + face_width + padding_x)
    crop_bottom = min(height, top + face_height + padding_y)

    # 最小サイズ確保（50x50 ピクセル未満なら中心から切り出し）
    min_size = 50
    if (crop_right - crop_left) < min_size or (crop_bottom - crop_top) < min_size:
        center_x = left + face_width // 2
        center_y = top + face_height // 2
        half_size = min_size // 2

        crop_left = max(0, center_x - half_size)
        crop_top = max(0, center_y - half_size)
        crop_right = min(width, center_x + half_size)
        crop_bottom = min(height, center_y + half_size)

    return image.crop((crop_left, crop_top, crop_right, crop_bottom))


def crop_all_faces(
    image: Image.Image, face_details: list[dict[str, Any]],
) -> list[tuple[Image.Image, int]]:
    """画像から全顔をクロップし、(画像, 元インデックス) のリストを返す"""
    cropped_faces: list[tuple[Image.Image, int]] = []
    for i, face_detail in enumerate(face_details):
        try:
            cropped_face = crop_face_from_image(image, face_detail)
            if cropped_face.size[0] >= 50 and cropped_face.size[1] >= 50:
                cropped_faces.append((cropped_face, i))
        except Exception:
            continue
    return cropped_faces


def face_image_to_bytes(
    face_image: Image.Image, format: str = "JPEG",
) -> bytes:
    """顔画像をバイト列に変換"""
    buffer = io.BytesIO()
    face_image.save(buffer, format=format)
    return buffer.getvalue()
