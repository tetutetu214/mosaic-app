"""
顔登録状態管理モジュール
"""
from typing import Dict, Any, Optional
import json


# メモリ内での簡単な状態管理（本格運用時はDynamoDBを使用）
_registration_state: Dict[str, bool] = {}


def set_registration_mode(user_id: str, enabled: bool) -> None:
    """ユーザーの登録モードを設定"""
    _registration_state[user_id] = enabled


def is_registration_mode(user_id: str) -> bool:
    """ユーザーが登録モード中かチェック"""
    return _registration_state.get(user_id, False)


def clear_registration_mode(user_id: str) -> None:
    """ユーザーの登録モードを解除"""
    _registration_state.pop(user_id, None)
