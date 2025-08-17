"""
顔コレクション管理モジュール
"""
import boto3
from typing import List, Dict, Any, Optional


def search_face_in_collection(bucket: str, key: str, collection_id: str, face_bbox: Dict[str, float]) -> List[Dict[str, Any]]:
    """指定された顔領域で登録済み顔を検索"""
    rekognition = boto3.client('rekognition')
    
    try:
        # 顔領域を指定して検索
        response = rekognition.search_faces_by_image(
            CollectionId=collection_id,
            Image={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            },
            FaceMatchThreshold=50.0,  # 閾値を下げる
            MaxFaces=10
        )
        
        print(f"DEBUG: Individual face search response: {response}")
        return response.get('FaceMatches', [])
    except Exception as e:
        print(f"DEBUG: Face search failed: {str(e)}")
        return []


def search_known_faces(bucket: str, key: str, collection_id: str) -> List[Dict[str, Any]]:
    """登録済み顔の検索（後方互換性のため残存）"""
    rekognition = boto3.client('rekognition')
    
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=collection_id,
            Image={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            },
            FaceMatchThreshold=50.0,
            MaxFaces=10
        )
        
        return response.get('FaceMatches', [])
    except rekognition.exceptions.InvalidParameterException:
        return []


def add_face_to_collection(bucket: str, key: str, collection_id: str) -> str:
    """顔をコレクションに追加"""
    rekognition = boto3.client('rekognition')
    
    response = rekognition.index_faces(
        CollectionId=collection_id,
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': key
            }
        },
        MaxFaces=1,
        QualityFilter='AUTO'
    )
    
    if response['FaceRecords']:
        return response['FaceRecords'][0]['Face']['FaceId']
    else:
        raise ValueError("No face detected in the image")
