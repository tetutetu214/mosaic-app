"""
顔照合モジュール
"""
from typing import List, Dict, Any


def filter_known_faces(detected_faces: List[Dict[str, Any]], known_face_matches: List[Dict[str, Any]], similarity_threshold: float = 85.0) -> List[Dict[str, Any]]:
    """
    検出された顔から登録済み顔を除外
    
    Args:
        detected_faces: Rekognitionで検出された顔のリスト
        known_face_matches: 登録済み顔との照合結果
        similarity_threshold: 類似度閾値
        
    Returns:
        List[Dict[str, Any]]: モザイクをかける顔のリスト
    """
    if not known_face_matches:
        return detected_faces
    
    faces_to_mosaic = []
    
    for detected_face in detected_faces:
        is_known_face = False
        
        for match in known_face_matches:
            if match['Similarity'] >= similarity_threshold:
                if _faces_overlap(detected_face['BoundingBox'], match['Face']['BoundingBox']):
                    is_known_face = True
                    break
        
        if not is_known_face:
            faces_to_mosaic.append(detected_face)
    
    return faces_to_mosaic


def _faces_overlap(bbox1: Dict[str, float], bbox2: Dict[str, float], overlap_threshold: float = 0.5) -> bool:
    """
    2つの顔領域が重複しているかチェック
    """
    x1_min, y1_min = bbox1['Left'], bbox1['Top']
    x1_max, y1_max = x1_min + bbox1['Width'], y1_min + bbox1['Height']
    
    x2_min, y2_min = bbox2['Left'], bbox2['Top']
    x2_max, y2_max = x2_min + bbox2['Width'], y2_min + bbox2['Height']
    
    overlap_x = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
    overlap_y = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
    overlap_area = overlap_x * overlap_y
    
    area1 = bbox1['Width'] * bbox1['Height']
    area2 = bbox2['Width'] * bbox2['Height']
    
    union_area = area1 + area2 - overlap_area
    if union_area == 0:
        return False
    
    iou = overlap_area / union_area
    return iou >= overlap_threshold
