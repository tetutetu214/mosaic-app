"""
顔照合モジュール
"""
from typing import List, Dict, Any


def filter_known_faces(detected_faces: List[Dict[str, Any]], bucket: str, key: str, collection_id: str, similarity_threshold: float = 70.0) -> List[Dict[str, Any]]:
    """
    検出された顔から登録済み顔を除外
    Rekognitionの制約により、登録済み顔が見つかった場合は最初の検出顔を除外
    """
    from collection_manager import search_known_faces
    
    print(f"DEBUG: detected_faces count: {len(detected_faces)}")
    
    known_face_matches = search_known_faces(bucket, key, collection_id)
    print(f"DEBUG: known_face_matches count: {len(known_face_matches)}")
    
    if not known_face_matches:
        print("DEBUG: No known faces found, returning all detected faces")
        return detected_faces
    
    # 登録済み顔との照合があった場合の処理
    for match in known_face_matches:
        similarity = match['Similarity']
        print(f"DEBUG: Found match with similarity: {similarity}")
        
        if similarity >= similarity_threshold:
            print("DEBUG: Known face detected, excluding first face from mosaic")
            # 最初の顔（通常は最も信頼度が高い）を除外
            return detected_faces[1:] if len(detected_faces) > 1 else []
    
    print("DEBUG: No high-similarity matches, returning all detected faces")
    return detected_faces
