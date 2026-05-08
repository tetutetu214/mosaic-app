"""顔コレクション管理モジュール"""
from typing import Any

import boto3


def search_known_faces(
    bucket: str, key: str, collection_id: str,
) -> list[dict[str, Any]]:
    """登録済み顔をコレクションから検索"""
    rekognition = boto3.client("rekognition")
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=collection_id,
            Image={"S3Object": {"Bucket": bucket, "Name": key}},
            FaceMatchThreshold=0.0,
            MaxFaces=3,
        )
        return response.get("FaceMatches", [])
    except rekognition.exceptions.InvalidParameterException:
        # 画像から顔が検出できない or コレクション未存在
        return []


def add_face_to_collection(
    bucket: str,
    key: str,
    collection_id: str,
    external_image_id: str | None = None,
) -> str:
    """顔をコレクションに追加し、face_id を返す。

    external_image_id を指定すると、Rekognition 側に同じ ID 付きで保存される。
    本プロジェクトでは LINE messageId を渡し、再処理時の冪等性確認に使う。
    """
    rekognition = boto3.client("rekognition")
    kwargs: dict[str, Any] = {
        "CollectionId": collection_id,
        "Image": {"S3Object": {"Bucket": bucket, "Name": key}},
        "MaxFaces": 1,
        "QualityFilter": "AUTO",
    }
    if external_image_id is not None:
        kwargs["ExternalImageId"] = external_image_id

    response = rekognition.index_faces(**kwargs)
    if response.get("FaceRecords"):
        return response["FaceRecords"][0]["Face"]["FaceId"]
    raise ValueError("No face detected in the image")
