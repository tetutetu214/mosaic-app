"""
モザイク処理モジュール
"""
import boto3
from PIL import Image
from typing import List, Dict, Any


def apply_mosaic(image: Image.Image, face_boxes: List[Dict[str, Any]], mosaic_strength: int = 20) -> Image.Image:
    """基本的なモザイク処理（強度アップ）"""
    result_image = image.copy()
    
    for face in face_boxes:
        bbox = face['BoundingBox']
        # 相対座標を絶対座標に変換
        width, height = image.size
        left = int(bbox['Left'] * width)
        top = int(bbox['Top'] * height)
        right = int((bbox['Left'] + bbox['Width']) * width)
        bottom = int((bbox['Top'] + bbox['Height']) * height)
        
        # 顔部分を切り出し
        face_region = result_image.crop((left, top, right, bottom))
        
        # モザイク処理（縮小→拡大）強度を上げた
        small_size = (max(1, (right - left) // mosaic_strength), 
                      max(1, (bottom - top) // mosaic_strength))
        face_region = face_region.resize(small_size, Image.NEAREST)
        face_region = face_region.resize((right - left, bottom - top), Image.NEAREST)
        
        # 元画像に貼り付け
        result_image.paste(face_region, (left, top))
    
    return result_image


def detect_faces(bucket: str, key: str) -> List[Dict[str, Any]]:
    """顔検出"""
    rekognition = boto3.client('rekognition')
    
    response = rekognition.detect_faces(
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': key
            }
        },
        Attributes=['DEFAULT']
    )
    
    return response['FaceDetails']
