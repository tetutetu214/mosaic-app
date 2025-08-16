"""
メイン処理関数
"""
import json
import logging
import os
from typing import Dict, Any

from config import get_settings
from mosaic_processor import detect_faces, apply_mosaic
from collection_manager import search_known_faces

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda エントリーポイント"""
    try:
        # 設定取得
        settings = get_settings()
        
        # LINE Webhookイベントかチェック
        if 'body' in event and 'headers' in event:
            return process_line_webhook(event, settings)
        
        # デフォルトレスポンス
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Mosaic App is running'})
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }


def process_line_webhook(event: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    """LINE Webhook処理"""
    try:
        # リクエストボディ解析
        body = json.loads(event['body'])
        
        # イベント処理
        for line_event in body.get('events', []):
            if line_event.get('type') == 'message':
                message = line_event.get('message', {})
                if message.get('type') == 'image':
                    # 画像メッセージ処理
                    process_image_message(line_event, settings)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok'})
        }
        
    except Exception as e:
        logger.error(f"Error processing LINE webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Webhook processing failed'})
        }


def process_image_message(line_event: Dict[str, Any], settings: Dict[str, Any]) -> None:
    """画像メッセージ処理"""
    from image_handler import process_image_message as handle_image
    handle_image(line_event, settings)
