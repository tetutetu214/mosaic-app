"""
config.py のテスト
"""
import pytest
import os
import sys
from unittest.mock import patch

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from config import get_settings, validate_settings


class TestConfig:
    """設定管理のテスト"""
    
    @patch.dict(os.environ, {
        'AWS_REGION': 'us-east-1',
        'S3_BUCKET_NAME': 'test-bucket',
        'REKOGNITION_COLLECTION_ID': 'test-collection',
        'MOSAIC_MODE': 'exclude',
        'LINE_CHANNEL_ACCESS_TOKEN': 'test-token',
        'LINE_CHANNEL_SECRET': 'test-secret'
    })
    def test_get_settings_success(self):
        """正常な環境変数設定時のテスト"""
        settings = get_settings()
        
        assert settings['aws_region'] == 'us-east-1'
        assert settings['s3_bucket_name'] == 'test-bucket'
        assert settings['rekognition_collection_id'] == 'test-collection'
        assert settings['mosaic_mode'] == 'exclude'
        assert settings['line_channel_access_token'] == 'test-token'
        assert settings['line_channel_secret'] == 'test-secret'
    
    def test_get_settings_missing_env(self):
        """環境変数が不足している場合のテスト"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variables"):
                get_settings()
    
    def test_validate_mosaic_mode_valid(self):
        """有効なモザイクモードのテスト"""
        validate_settings({'mosaic_mode': 'all'})
        validate_settings({'mosaic_mode': 'exclude'})
    
    def test_validate_mosaic_mode_invalid(self):
        """無効なモザイクモードのテスト"""
        with pytest.raises(ValueError, match="Invalid mosaic_mode"):
            validate_settings({'mosaic_mode': 'invalid'})
