"""
テキストメッセージハンドラー
"""
import boto3
from typing import Dict, Any
from collection_manager import add_face_to_collection


def process_text_message(line_event: Dict[str, Any], settings: Dict[str, Any]) -> None:
    """テキストメッセージ処理"""
    message_text = line_event['message']['text'].strip()
    reply_token = line_event['replyToken']
    
    if message_text == "登録":
        # ユーザーIDを取得
        user_id = line_event.get("source", {}).get("userId", "unknown")
        # 登録モードを開始
        from registration_state import set_registration_mode
        set_registration_mode(user_id, True)
        send_registration_instruction(reply_token, settings)
    elif message_text == "状態":
        send_status_info(reply_token, settings)
    else:
        # 不明なコマンドの場合は何もしない
        pass


def send_registration_instruction(reply_token: str, settings: Dict[str, Any]) -> None:
    """顔登録の手順を送信"""
    from image_handler import send_line_reply
    
    instruction_text = """顔登録モード
次に送信する画像から顔を登録します。
1枚の画像に1つの顔のみが写った写真を送信してください。"""
    
    send_line_reply(reply_token, instruction_text, settings)


def send_status_info(reply_token: str, settings: Dict[str, Any]) -> None:
    """現在の状態情報を送信"""
    from image_handler import send_line_reply
    
    # 登録済み顔の数を取得
    face_count = get_registered_face_count(settings['rekognition_collection_id'])
    
    status_text = f"""モザイクアプリ状態
モード: {settings['mosaic_mode']}
登録済み顔: {face_count}個

コマンド:
「登録」- 顔を登録
「状態」- 現在の状態確認"""
    
    send_line_reply(reply_token, status_text, settings)


def get_registered_face_count(collection_id: str) -> int:
    """登録済み顔の数を取得"""
    rekognition = boto3.client('rekognition')
    
    try:
        response = rekognition.list_faces(CollectionId=collection_id)
        return len(response.get('Faces', []))
    except Exception:
        return 0
