"""
画像処理ハンドラー（顔数制限対応）
"""
import boto3
import requests
from PIL import Image
import io
import uuid
from typing import Dict, Any

from mosaic_processor import detect_faces, apply_mosaic


def process_image_message(line_event: Dict[str, Any], settings: Dict[str, Any]) -> None:
    """画像メッセージ処理（顔数制限対応）"""
    user_id = line_event.get("source", {}).get("userId", "unknown")
    
    # 登録モードかチェック
    from registration_state import is_registration_mode, clear_registration_mode
    if is_registration_mode(user_id):
        process_face_registration(line_event, settings, user_id)
        return
    
    message_id = line_event['message']['id']
    reply_token = line_event['replyToken']
    
    try:
        # 1. LINE APIから画像ダウンロード
        image_data = download_image_from_line(message_id, settings)
        
        # 2. S3にアップロード
        image_key = f"input/{uuid.uuid4()}.jpg"
        upload_to_s3(image_data, image_key, settings['s3_bucket_name'])
        
        # 3. 顔検出
        faces = detect_faces(settings['s3_bucket_name'], image_key)
        
        if not faces:
            send_line_reply(reply_token, "顔が検出されませんでした。", settings)
            return
        
        # 4. モザイク処理（顔数制限対応）
        if settings['mosaic_mode'] == 'exclude':
            # 顔数制限付きの登録済み顔除外
            from face_matcher import filter_known_faces_with_limit
            
            # PIL画像オブジェクト作成
            original_image = Image.open(io.BytesIO(image_data))
            
            faces_to_mosaic = filter_known_faces_with_limit(
                faces, 
                original_image,
                settings["s3_bucket_name"], 
                f"faces/{uuid.uuid4()}",  # 一意なプレフィックス
                settings["rekognition_collection_id"],
                face_limit=5,
                similarity_threshold=50.0  # 70.0から50.0に変更
            )
        else:
            # 全ての顔にモザイク
            faces_to_mosaic = faces
        
        # 5. 画像にモザイク適用
        image = Image.open(io.BytesIO(image_data))
        mosaic_image = apply_mosaic(image, faces_to_mosaic)
        
        # 6. 処理済み画像をS3にアップロード
        output_key = f"output/{uuid.uuid4()}.jpg"
        output_buffer = io.BytesIO()
        mosaic_image.save(output_buffer, format='JPEG')
        upload_to_s3(output_buffer.getvalue(), output_key, settings['s3_bucket_name'])
        
        # 7. 署名付きURLでLINEに画像を返信
        send_secure_image_reply(reply_token, settings['s3_bucket_name'], output_key, settings)
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        send_line_reply(reply_token, "画像処理中にエラーが発生しました。", settings)


def download_image_from_line(message_id: str, settings: Dict[str, Any]) -> bytes:
    """LINE APIから画像をダウンロード"""
    headers = {
        'Authorization': f'Bearer {settings["line_channel_access_token"]}'
    }
    
    response = requests.get(
        f'https://api-data.line.me/v2/bot/message/{message_id}/content',
        headers=headers
    )
    
    response.raise_for_status()
    return response.content


def upload_to_s3(image_data: bytes, key: str, bucket: str) -> None:
    """S3に画像をアップロード"""
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=image_data,
        ContentType='image/jpeg'
    )


def generate_presigned_url(bucket: str, key: str, expiration: int = 3600) -> str:
    """署名付きURLを生成（1時間有効）"""
    s3 = boto3.client('s3')
    
    try:
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        return presigned_url
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        raise


def send_line_reply(reply_token: str, message: str, settings: Dict[str, Any]) -> None:
    """LINEテキストメッセージ返信"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {settings["line_channel_access_token"]}'
    }
    
    data = {
        'replyToken': reply_token,
        'messages': [
            {
                'type': 'text',
                'text': message
            }
        ]
    }
    
    requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers=headers,
        json=data
    )


def send_secure_image_reply(reply_token: str, bucket: str, key: str, settings: Dict[str, Any]) -> None:
    """LINE画像メッセージ返信（署名付きURL使用）"""
    # 署名付きURLを生成（1時間有効）
    presigned_url = generate_presigned_url(bucket, key, expiration=3600)
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {settings["line_channel_access_token"]}'
    }
    
    data = {
        'replyToken': reply_token,
        'messages': [
            {
                'type': 'image',
                'originalContentUrl': presigned_url,
                'previewImageUrl': presigned_url
            }
        ]
    }
    
    requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers=headers,
        json=data
    )


def process_face_registration(line_event: Dict[str, Any], settings: Dict[str, Any], user_id: str) -> None:
    """顔登録処理"""
    message_id = line_event['message']['id']
    reply_token = line_event['replyToken']
    
    try:
        # 1. LINE APIから画像ダウンロード
        image_data = download_image_from_line(message_id, settings)
        
        # 2. S3にアップロード
        image_key = f"registration/{user_id}_{uuid.uuid4()}.jpg"
        upload_to_s3(image_data, image_key, settings['s3_bucket_name'])
        
        # 3. 顔検出
        faces = detect_faces(settings['s3_bucket_name'], image_key)
        
        if not faces:
            send_line_reply(reply_token, "顔が検出されませんでした。別の画像で再度お試しください。", settings)
            return
        
        if len(faces) > 1:
            send_line_reply(reply_token, "複数の顔が検出されました。1つの顔のみが写った画像を送信してください。", settings)
            return
        
        # 4. 顔をコレクションに登録
        from collection_manager import add_face_to_collection
        face_id = add_face_to_collection(
            settings['s3_bucket_name'], 
            image_key, 
            settings['rekognition_collection_id']
        )
        
        # 5. 登録モード解除
        from registration_state import clear_registration_mode
        clear_registration_mode(user_id)
        
        send_line_reply(reply_token, f"顔登録が完了しました。\n登録ID: {face_id[:8]}...", settings)
        
    except Exception as e:
        print(f"Error in face registration: {str(e)}")
        send_line_reply(reply_token, "顔登録中にエラーが発生しました。", settings)
        
        # エラー時も登録モード解除
        from registration_state import clear_registration_mode
        clear_registration_mode(user_id)
