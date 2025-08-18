# Mosaic App

LINEで送った写真の顔を自動でモザイク処理するサーバーレスアプリケーション

## 機能

- LINE Botに画像を送信すると、自動で顔を検出してモザイク処理
- 署名付きURLによるセキュアな画像配信
- 完全サーバーレス構成（AWS Lambda + API Gateway）
- Dockerコンテナベースのデプロイ
- **顔数制限付き個別照合**: 20人以下で個別照合、21人以上で全員モザイク

## アーキテクチャ

LINE Bot → API Gateway → Lambda → Rekognition → S3 Bucket

### 主要コンポーネント
- AWS Lambda: Python 3.12 + Docker
- API Gateway: Webhook エンドポイント
- S3: 画像ストレージ（プライベート）
- Rekognition: 顔検出AI + 個別顔照合
- ECR: Dockerイメージ管理

## 顔認識の仕組み

### 20人以下の場合（個別照合）
1. 各顔を個別に切り出し
2. S3にアップロードして個別照合
3. 類似度50%以上の最高スコアをユーザーとして認識
4. ユーザーの顔のみ除外、他はモザイク

### 21人以上の場合（全員モザイク）
- 処理時間とコスト考慮により個別照合を実行せず
- 全員にモザイクを適用

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


## テスト

### 単体テスト実行:
```bash
python -m pytest tests/ -v
```

### 特定のテストのみ実行:
```bash
bashpython -m pytest tests/test_face_cropper.py -v
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

小さい値: 弱いモザイク
大きい値: 強いモザイク（デフォルト: 20）

### モザイクモード

all: 全ての顔にモザイク
exclude: 登録済み顔を除外（顔数制限付き）

### 顔認識設定

類似度閾値: 50%（50%以上でユーザー認識）
顔数制限: 20人（20人以下で個別照合、21人以上で全員モザイク）
AWS Rekognition閾値: 0.0%（全ての類似度データを取得）