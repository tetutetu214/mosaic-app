"""顔照合モジュール（個別照合対応）"""
from typing import Any

from PIL import Image

from face_cropper import crop_all_faces, face_image_to_bytes
from collection_manager import search_known_faces


def filter_known_faces_with_limit(
    detected_faces: list[dict[str, Any]],
    original_image: Image.Image,
    bucket: str,
    key_prefix: str,
    collection_id: str,
    s3_client: Any,
    face_limit: int = 20,
    similarity_threshold: float = 50.0,
) -> list[dict[str, Any]]:
    """顔数制限付きの登録済み顔除外処理。

    顔数が face_limit を超える場合は全員モザイク（個別照合のコスト超過防止）。
    s3_client は boto3 S3 client（テスト時に差し替え可能）。
    """
    if len(detected_faces) > face_limit:
        return detected_faces

    return _filter_faces_individually(
        detected_faces,
        original_image,
        bucket,
        key_prefix,
        collection_id,
        similarity_threshold,
        s3_client,
    )


def _filter_faces_individually(
    detected_faces: list[dict[str, Any]],
    original_image: Image.Image,
    bucket: str,
    key_prefix: str,
    collection_id: str,
    similarity_threshold: float,
    s3_client: Any,
) -> list[dict[str, Any]]:
    """各顔を個別に照合して登録済み顔を除外する"""
    cropped_faces = crop_all_faces(original_image, detected_faces)
    matched_indices: set[int] = set()

    for cropped_face, original_index in cropped_faces:
        try:
            face_key = f"{key_prefix}/face_{original_index}.jpg"
            face_bytes = face_image_to_bytes(cropped_face)
            s3_client.put_object(
                Bucket=bucket,
                Key=face_key,
                Body=face_bytes,
                ContentType="image/jpeg",
            )

            matches = search_known_faces(bucket, face_key, collection_id)
            if matches:
                max_similarity = max(m.get("Similarity", 0) for m in matches)
                if max_similarity >= similarity_threshold:
                    matched_indices.add(original_index)
        except Exception:
            # 個別照合の失敗は致命的ではない（モザイク対象に残るだけ）
            continue

    if matched_indices:
        return [
            f for i, f in enumerate(detected_faces) if i not in matched_indices
        ]
    return detected_faces
