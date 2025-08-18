# Mosaic App
LINEで送った写真の顔を自動でモザイク処理するサーバーレスアプリケーション

## 使い方
### 基本操作
1. LINE友達追加でボットを追加
2. 写真を送信すると自動で登録者以外の顔にモザイクをかけて返信

### コマンド
- 登録: モザイクから除外したい顔を登録
- 状態: 現在の設定と登録済み顔数を確認

### 顔登録の流れ
1. 「登録」とメッセージ送信
2. 1人だけが写った顔写真を送信
3. 登録完了後、以降の写真では登録者の顔のみ除外される

### 注意事項
- 顔登録は1枚の写真に1人のみ
- 複数人が写った写真では登録できません
- 20人以下の写真で個別照合、21人以上では全員モザイク


## セットアップ
### 1. AWS環境構築
```bash
# ECRリポジトリ作成
aws ecr create-repository --repository-name mosaic-app

# Rekognitionコレクション作成
aws rekognition create-collection --collection-id your-collection-name

# S3バケット作成
aws s3 mb s3://your-bucket-name
```

### 2. LINE Developers設定
1. LINE Developersでプロバイダー作成
2. Channel Access TokenとChannel Secretを取得
3. Webhook URLを設定


### 3. デプロイ
```bash
# Dockerイメージビルド
docker build -t mosaic-app .

# ECRにプッシュ
docker tag mosaic-app:latest your-account.dkr.ecr.region.amazonaws.com/mosaic-app:latest
docker push your-account.dkr.ecr.region.amazonaws.com/mosaic-app:latest

# Lambda関数作成・更新
aws lambda create-function --function-name mosaic-app --code ImageUri=your-ecr-uri
```

### 4.環境変数設定 
```bash
S3_BUCKET_NAME=your-bucket-name
REKOGNITION_COLLECTION_ID=your-collection-name
MOSAIC_MODE=exclude
LINE_CHANNEL_ACCESS_TOKEN=your-line-token
LINE_CHANNEL_SECRET=your-line-secret
```


## 技術構成
### アーキテクチャ:
LINE Bot → API Gateway → Lambda → Rekognition → S3

### 主要技術:
- AWS Lambda (Python 3.12 + Docker)
- AWS Rekognition (顔検出・照合)
- S3 (プライベート画像ストレージ)

## テスト

### 単体テスト実行:
```bash
python -m pytest tests/ -v
```

### 特定のテストのみ実行:
```bash
python -m pytest tests/test_face_cropper.py -v
```

## プロジェクト構造
```shell
mosaic-app/
├── lambda-function/           # Lambda関数コード
│   ├── lambda_function.py    # メイン処理
│   ├── config.py            # 設定管理
│   ├── image_handler.py     # 画像処理（顔数制限対応）
│   ├── mosaic_processor.py  # モザイク処理
│   ├── face_cropper.py      # 顔切り出し処理
│   ├── face_matcher.py      # 個別顔照合処理
│   ├── collection_manager.py # 顔コレクション管理
│   ├── registration_state.py # 顔登録状態管理
│   ├── text_handler.py      # テキストメッセージ処理
│   ├── requirements.txt     # Lambda依存関係
│   └── __init__.py         # パッケージ初期化
├── tests/                   # テストコード
│   ├── test_collection_manager.py
│   ├── test_config.py
│   ├── test_face_cropper.py
│   ├── test_face_matcher.py
│   ├── test_image_handler.py
│   ├── test_image_handler_integration.py
│   ├── test_lambda_function.py
│   ├── test_mosaic_processor.py
│   ├── test_registration_state.py
│   └── test_text_handler.py
├── Dockerfile              # コンテナ定義
├── requirements-dev.txt    # 開発/テスト依存関係
├── pytest.ini            # pytest設定
├── trust-policy.json     # IAMロール信頼ポリシー
└── README.md             # このファイル
```

## 設定オプション
### モザイク強度調整
lambda-function/mosaic_processor.pyのmosaic_strengthを変更:
- 小さい値: 弱いモザイク
- 大きい値: 強いモザイク（デフォルト: 20）

### モザイクモード
環境変数 MOSAIC_MODE で変更:
- all: 全ての顔にモザイク
- exclude: 登録済み顔を除外（顔数制限付き）

### 顔認識設定
- 類似度閾値: 50%（lambda-function/image_handler.py で変更）
- 顔数制限: 20人（lambda-function/image_handler.py で変更）
- AWS Rekognition閾値: 0.0%（lambda-function/collection_manager.py で変更）