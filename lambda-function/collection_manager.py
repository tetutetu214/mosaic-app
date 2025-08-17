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
            FaceMatchThreshold=0.5,
            MaxFaces=3
        )
        
        matches = response.get('FaceMatches', [])
        
        # 類似度を全部ログ出力
        print(f"=== Face Recognition Results ===")
        print(f"Total matches found: {len(matches)}")
        for i, match in enumerate(matches):
            similarity = match.get('Similarity', 0)
            face_id = match.get('Face', {}).get('FaceId', 'unknown')
            print(f"Match {i+1}: FaceID={face_id}, Similarity={similarity:.2f}%")
        
        if not matches:
            print("No matching faces found in collection")
        
        return matches
        
    except rekognition.exceptions.InvalidParameterException:
        print("InvalidParameterException: No faces detected in image or collection not found")
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
