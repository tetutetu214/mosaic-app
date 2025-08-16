# Mosaic App

LINEで送った写真の顔を自動でモザイク処理するサーバーレスアプリケーション

## 機能

- LINE Botに画像を送信すると、自動で顔を検出してモザイク処理
- 署名付きURLによるセキュアな画像配信
- 完全サーバーレス構成（AWS Lambda + API Gateway）
- Dockerコンテナベースのデプロイ

## アーキテクチャ

LINE Bot → API Gateway → Lambda → Rekognition → S3 Bucket

### 主要コンポーネント
- AWS Lambda: Python 3.12 + Docker
- API Gateway: Webhook エンドポイント
- S3: 画像ストレージ（プライベート）
- Rekognition: 顔検出AI
- ECR: Dockerイメージ管理

## セキュリティ

- S3バケット: 完全プライベート（パブリックアクセス禁止）
- 画像配信: 署名付きURL（Presigned URL）で1時間限定アクセス
- 認証: AWS IAMによる署名済みリクエストのみ許可
- 環境変数: Lambda内で暗号化管理
- IAMロール: 最小権限の原則に従ったアクセス制御
- HTTPS: 全通信が暗号化済み

### 署名付きURLの仕組み
1. Lambda関数がS3オブジェクトの署名付きURLを生成
2. URLには一時的なアクセス権限が含まれる（1時間有効）
3. LINE APIに署名付きURLを返信
4. ユーザーは期限内のみ画像にアクセス可能
5. 期限切れ後は自動的にアクセス不可

重要: S3バケットを公開設定にする必要は一切ありません

## テスト

単体テスト実行:
python -m pytest tests/ -v

## プロジェクト構造

mosaic-app/
├── lambda-function/           # Lambda関数コード
│   ├── lambda_function.py    # メイン処理
│   ├── config.py            # 設定管理
│   ├── image_handler.py     # 画像処理
│   ├── mosaic_processor.py  # モザイク処理
│   └── collection_manager.py # 顔コレクション管理
├── tests/                   # テストコード
├── Dockerfile              # コンテナ定義
├── requirements.txt        # 本番依存関係
├── requirements-dev.txt    # 開発依存関係
├── env-vars.json          # 環境変数設定
└── README.md             # このファイル

## 設定オプション

### モザイク強度調整
lambda-function/mosaic_processor.pyのmosaic_strengthを変更:
- 小さい値: 弱いモザイク
- 大きい値: 強いモザイク（デフォルト: 10）

### モザイクモード
- all: 全ての顔にモザイク（デフォルト）
- exclude: 登録済み顔を除外（今後実装予定）

## ライセンス

MIT License
