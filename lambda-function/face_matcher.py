"""
顔照合モジュール（個別照合対応）
"""
import uuid
from typing import List, Dict, Any, Tuple
from PIL import Image

from face_cropper import crop_all_faces, face_image_to_bytes


def filter_known_faces_with_limit(
    detected_faces: List[Dict[str, Any]], 
    original_image: Image.Image,
    bucket: str, 
    key_prefix: str,
    collection_id: str,
    face_limit: int = 5,
    similarity_threshold: float = 50.0  # 70.0から50.0に変更
) -> List[Dict[str, Any]]:
    """
    顔数制限付きの登録済み顔除外処理
    
    Args:
        detected_faces: 検出された全ての顔
        original_image: 元画像
        bucket: S3バケット名
        key_prefix: S3キーのプレフィックス
        collection_id: Rekognitionコレクション ID
        face_limit: 個別照合を行う顔数の上限
        similarity_threshold: 一致判定の閾値
    
    Returns:
        モザイク対象の顔リスト
    """
    print(f"DEBUG: detected_faces count: {len(detected_faces)}")
    print(f"DEBUG: face_limit: {face_limit}")
    
    # 顔数制限チェック
    if len(detected_faces) > face_limit:
        print(f"DEBUG: Too many faces ({len(detected_faces)} > {face_limit}), applying mosaic to all")
        return detected_faces
    
    # 個別照合処理
    return filter_faces_individually(
        detected_faces, 
        original_image, 
        bucket, 
        key_prefix, 
        collection_id, 
        similarity_threshold
    )


def filter_faces_individually(
    detected_faces: List[Dict[str, Any]], 
    original_image: Image.Image,
    bucket: str, 
    key_prefix: str,
    collection_id: str,
    similarity_threshold: float = 50.0
) -> List[Dict[str, Any]]:
    """
    各顔を個別に照合して登録済み顔を除外
    """
    from collection_manager import search_known_faces
    from image_handler import upload_to_s3
    
    print(f"DEBUG: Starting individual face processing for {len(detected_faces)} faces")
    
    # 全ての顔をクロップ
    cropped_faces = crop_all_faces(original_image, detected_faces)
    print(f"DEBUG: Successfully cropped {len(cropped_faces)} faces")
    
    faces_to_mosaic = []
    matched_indices = set()

    # 各顔を個別に照合
    for i, (cropped_face, original_index) in enumerate(cropped_faces):
        try:
            print(f"DEBUG: Processing face {i+1}/{len(cropped_faces)}")

            # 顔画像をS3にアップロード
            face_key = f"{key_prefix}/face_{original_index}_{uuid.uuid4()}.jpg"
            face_bytes = face_image_to_bytes(cropped_face)
            print(f"DEBUG: Uploading face {i+1} to S3")
            upload_to_s3(face_bytes, face_key, bucket)

            # 個別照合
            print(f"DEBUG: Searching face {i+1} in collection")
            matches = search_known_faces(bucket, face_key, collection_id)
            print(f"DEBUG: Face {i+1} search completed")

            if matches:
                # 最高類似度を取得
                max_similarity = max(match.get('Similarity', 0) for match in matches)
                print(f"DEBUG: Face {original_index} similarity: {max_similarity:.2f}%")

                # 閾値以上なら登録済み顔として記録
                if max_similarity >= similarity_threshold:
                    matched_indices.add(original_index)
                    print(f"DEBUG: Face {original_index} matched as registered face")
            else:
                print(f"DEBUG: Face {original_index} no matches found")

        except Exception as e:
            print(f"ERROR: Failed processing face {i+1}: {str(e)}")
            import traceback
            print(f"ERROR traceback: {traceback.format_exc()}")
            continue

    print(f"DEBUG: Individual processing completed")
    print(f"DEBUG: {len(matched_indices)} registered faces found: {matched_indices}")

    # 結果判定: 登録済み顔を全て除外
    if matched_indices:
        for i, face in enumerate(detected_faces):
            if i not in matched_indices:
                faces_to_mosaic.append(face)
    else:
        print(f"DEBUG: No registered faces found, applying mosaic to all faces")
        faces_to_mosaic = detected_faces

    print(f"DEBUG: {len(faces_to_mosaic)} faces will be mosaicked")
    return faces_to_mosaic

def filter_known_faces(detected_faces: List[Dict[str, Any]], bucket: str, key: str, collection_id: str, similarity_threshold: float = 50.0) -> List[Dict[str, Any]]:
    """
    従来の登録済み顔除外処理（後方互換性のため残す）
    """
    from collection_manager import search_known_faces
    
    print(f"DEBUG: detected_faces count: {len(detected_faces)}")
    
    known_face_matches = search_known_faces(bucket, key, collection_id)
    print(f"DEBUG: known_face_matches count: {len(known_face_matches)}")
    
    if not known_face_matches:
        print("DEBUG: No known faces found, returning all detected faces")
        return detected_faces
    
    # 一番高い類似度のマッチを見つける
    best_match = max(known_face_matches, key=lambda x: x.get('Similarity', 0))
    best_similarity = best_match.get('Similarity', 0)
    
    print(f"DEBUG: Best match similarity: {best_similarity}")
    
    # 閾値以上の場合のみユーザーの顔として除外
    if best_similarity >= similarity_threshold:
        print("DEBUG: Excluding highest similarity face (user's face) from mosaic")
        # 最初の顔（通常は最も信頼度が高い）を除外
        return detected_faces[1:] if len(detected_faces) > 1 else []
    else:
        print("DEBUG: No high-similarity matches, returning all detected faces")
        return detected_faces
