"""
顔コレクション管理モジュール
"""
import boto3
from typing import List, Dict, Any, Optional


def search_known_faces(bucket: str, key: str, collection_id: str) -> List[Dict[str, Any]]:
    """登録済み顔の検索"""
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
            FaceMatchThreshold=70.0,
            MaxFaces=10
        )
        
        return response.get('FaceMatches', [])
    except rekognition.exceptions.InvalidParameterException:
        # 顔が見つからない場合
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
