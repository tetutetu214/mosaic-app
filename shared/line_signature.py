"""LINE Webhook 署名検証ユーティリティ"""
import base64
import hashlib
import hmac


def verify_signature(body: str, signature: str, channel_secret: str) -> bool:
    """X-Line-Signature ヘッダの妥当性を検証する。

    LINE Messaging API は webhook ボディを HMAC-SHA256 でハッシュし、
    Base64 にエンコードしたものを X-Line-Signature ヘッダに乗せて送信する。
    本関数は同じ手順で署名を再計算し、ヘッダ値とタイミング攻撃に強い比較を行う。
    """
    if not body or not signature or not channel_secret:
        return False
    expected = base64.b64encode(
        hmac.new(
            channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)
