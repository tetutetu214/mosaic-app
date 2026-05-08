"""LINE Messaging API クライアント"""
import requests


class LineApiClient:
    """LINE Messaging API のラッパー（reply / push / content download）"""

    REPLY_URL = "https://api.line.me/v2/bot/message/reply"
    PUSH_URL = "https://api.line.me/v2/bot/message/push"
    CONTENT_URL_TEMPLATE = (
        "https://api-data.line.me/v2/bot/message/{message_id}/content"
    )

    DEFAULT_TIMEOUT = 5
    DOWNLOAD_TIMEOUT = 30

    def __init__(self, channel_access_token: str) -> None:
        self._token = channel_access_token

    @property
    def _json_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    @property
    def _auth_only_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def reply(self, reply_token: str, text: str) -> None:
        """reply token でテキストを返信する"""
        payload = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text}],
        }
        response = requests.post(
            self.REPLY_URL,
            headers=self._json_headers,
            json=payload,
            timeout=self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    def push_text(self, user_id: str, text: str) -> None:
        """ユーザーにテキストを Push する"""
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": text}],
        }
        response = requests.post(
            self.PUSH_URL,
            headers=self._json_headers,
            json=payload,
            timeout=self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    def push_image(
        self, user_id: str, original_url: str, preview_url: str
    ) -> None:
        """ユーザーに画像メッセージを Push する"""
        payload = {
            "to": user_id,
            "messages": [
                {
                    "type": "image",
                    "originalContentUrl": original_url,
                    "previewImageUrl": preview_url,
                }
            ],
        }
        response = requests.post(
            self.PUSH_URL,
            headers=self._json_headers,
            json=payload,
            timeout=self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    def download_content(self, message_id: str) -> bytes:
        """LINE 上の画像コンテンツをダウンロードする"""
        url = self.CONTENT_URL_TEMPLATE.format(message_id=message_id)
        response = requests.get(
            url,
            headers=self._auth_only_headers,
            timeout=self.DOWNLOAD_TIMEOUT,
        )
        response.raise_for_status()
        return response.content
