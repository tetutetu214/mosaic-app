"""モザイク処理モジュール"""
from typing import Any

import boto3
from PIL import Image


def apply_mosaic(
    image: Image.Image,
    face_boxes: list[dict[str, Any]],
    mosaic_strength: int = 20,
) -> Image.Image:
    """検出された顔領域にモザイクを適用する"""
    result_image = image.copy()
    width, height = image.size

    for face in face_boxes:
        bbox = face["BoundingBox"]
        # 相対座標 → 絶対座標
        left = int(bbox["Left"] * width)
        top = int(bbox["Top"] * height)
        right = int((bbox["Left"] + bbox["Width"]) * width)
        bottom = int((bbox["Top"] + bbox["Height"]) * height)

        # 顔部分を切り出し
        face_region = result_image.crop((left, top, right, bottom))

        # モザイク処理（縮小→拡大、強度 mosaic_strength）
        small_size = (
            max(1, (right - left) // mosaic_strength),
            max(1, (bottom - top) // mosaic_strength),
        )
        face_region = face_region.resize(small_size, Image.NEAREST)
        face_region = face_region.resize(
            (right - left, bottom - top), Image.NEAREST,
        )

        result_image.paste(face_region, (left, top))

    return result_image


def detect_faces(bucket: str, key: str) -> list[dict[str, Any]]:
    """Rekognition で顔検出（S3 オブジェクト指定）"""
    rekognition = boto3.client("rekognition")
    response = rekognition.detect_faces(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        Attributes=["DEFAULT"],
    )
    return response["FaceDetails"]
