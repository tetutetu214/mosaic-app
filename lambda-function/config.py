"""
設定管理モジュール
"""
import os
from typing import Dict, Any


def get_settings() -> Dict[str, Any]:
    """
    環境変数から設定を取得
    
    Returns:
        Dict[str, Any]: 設定辞書
        
    Raises:
        ValueError: 必須環境変数が不足している場合
    """
    required_vars = [
        'S3_BUCKET_NAME', 
        'REKOGNITION_COLLECTION_ID',
        'MOSAIC_MODE',
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET'
    ]
    
    settings = {}
    missing_vars = []
    
    # AWS_REGIONは自動的に設定されるので個別処理
    settings['aws_region'] = os.environ.get('AWS_REGION', 'us-east-1')
    
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        else:
            # キーを小文字のスネークケースに変換
            key = var.lower()
            settings[key] = value
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    validate_settings(settings)
    return settings


def validate_settings(settings: Dict[str, Any]) -> None:
    """
    設定値の検証
    
    Args:
        settings: 設定辞書
        
    Raises:
        ValueError: 無効な設定値がある場合
    """
    # モザイクモードの検証
    valid_modes = ['all', 'exclude']
    mosaic_mode = settings.get('mosaic_mode')
    
    if mosaic_mode not in valid_modes:
        raise ValueError(f"Invalid mosaic_mode: {mosaic_mode}. Must be one of {valid_modes}")
