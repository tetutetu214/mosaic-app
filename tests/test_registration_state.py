"""
registration_state.py のテスト
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda-function'))

from registration_state import set_registration_mode, is_registration_mode, clear_registration_mode


class TestRegistrationState:
    """顔登録状態管理のテスト"""
    
    def test_set_and_check_registration_mode(self):
        """登録モード設定とチェックのテスト"""
        user_id = "test-user-123"
        
        # 初期状態はFalse
        assert is_registration_mode(user_id) is False
        
        # 登録モード開始
        set_registration_mode(user_id, True)
        assert is_registration_mode(user_id) is True
        
        # 登録モード解除
        set_registration_mode(user_id, False)
        assert is_registration_mode(user_id) is False
    
    def test_clear_registration_mode(self):
        """登録モードクリアのテスト"""
        user_id = "test-user-456"
        
        # 登録モード開始
        set_registration_mode(user_id, True)
        assert is_registration_mode(user_id) is True
        
        # 登録モードクリア
        clear_registration_mode(user_id)
        assert is_registration_mode(user_id) is False
    
    def test_multiple_users(self):
        """複数ユーザーの状態管理テスト"""
        user1 = "user-1"
        user2 = "user-2"
        
        # user1のみ登録モード
        set_registration_mode(user1, True)
        
        assert is_registration_mode(user1) is True
        assert is_registration_mode(user2) is False
        
        # user2も登録モード
        set_registration_mode(user2, True)
        
        assert is_registration_mode(user1) is True
        assert is_registration_mode(user2) is True
        
        # user1のみクリア
        clear_registration_mode(user1)
        
        assert is_registration_mode(user1) is False
        assert is_registration_mode(user2) is True
