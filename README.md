# Mosaic App - Exclude Mode

LINEで送った写真の自分以外の顔を自動でモザイク処理するサーバーレスアプリケーション

## 機能

- LINE Botに画像を送信すると、自動で顔を検出
- 登録済みの顔（自分）を除外してモザイク処理
- 署名付きURLによるセキュアな画像配信
- 完全サーバーレス構成（AWS Lambda + API Gateway）

## 新機能（v2.0）

- 顔登録機能：「登録」メッセージで自分の顔を登録
- 除外モード：登録済み顔を認識して自動除外
- 状態確認：「状態」メッセージで登録状況確認

## 使用方法

1. LINE Botに「登録」と送信
2. 自分の顔が1つだけ写った画像を送信
3. 登録完了後、複数人の写真を送信
4. 自分以外の顔にモザイクがかかった画像が返信される

## アーキテクチャ

LINE Bot → API Gateway → Lambda → Rekognition → S3 Bucket
                                  ↓
                           Face Collection

### 主要コンポーネント
- AWS Lambda: Python 3.12 + Docker
- API Gateway: Webhook エンドポイント
- S3: 画像ストレージ（プライベート）
- Rekognition: 顔検出・照合AI
- Face Collection: 登録済み顔データベース

## テスト

単体テスト実行:
python -m pytest tests/ -v

## プロジェクト構造

mosaic-app-exclude/
├── lambda-function/
│   ├── lambda_function.py      # メイン処理
│   ├── image_handler.py        # 画像・顔登録処理
│   ├── text_handler.py         # テキストメッセージ処理
│   ├── face_matcher.py         # 顔照合ロジック
│   ├── registration_state.py   # 登録状態管理
│   └── ...
├── tests/                      # 全機能のテストコード
└── ...

## 設定オプション

### モザイク強度調整
lambda-function/mosaic_processor.pyのmosaic_strength: 20（強め）

### モザイクモード
exclude: 登録済み顔を除外（このバージョンの機能）

## ライセンス

MIT License
