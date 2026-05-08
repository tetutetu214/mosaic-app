# mosaic-app — プロジェクト固有設定

## プロジェクト概要
LINE で送った写真の顔を自動でモザイク処理して返すサーバーレスアプリ。「登録」コマンドで除外したい顔を Rekognition コレクションに登録しておくと、その人以外にモザイクをかける。

## 現状の構成（同期版）
- LINE Bot → API Gateway (REST `mosaic-app-api`) → Lambda (`mosaic-app`、コンテナイメージ) → Rekognition + S3
- Lambda はコンテナ Image 構成（Python 3.12、`public.ecr.aws/lambda/python:3.12` ベース）
- Lambda メモリ 512MB / タイムアウト 30秒 / x86_64
- ECR リポジトリ `mosaic-app`（us-east-1）

## 進行中のリファクタ（Phase 2: 非同期化）
詳細は `docs/plan.md`。要点:
- 受信用 Lambda と画像処理用 Lambda を分離
- SQS Standard で非同期化
- IaC は AWS SAM
- 既存リソースを残したまま並行運用 → LINE Webhook URL 切替で本番化

## 技術スタック
- 言語: Python 3.12
- 主要ライブラリ: Pillow（画像処理）, boto3（AWS SDK）, requests（LINE API 呼び出し）
- インフラ: AWS Lambda（コンテナイメージ）, API Gateway REST, S3, Rekognition
- リージョン: us-east-1

## ディレクトリ構造（現在）
```
mosaic-app/
├── lambda-function/       # Lambda 関数コード（同期版）
├── tests/                 # pytest テスト
├── docs/                  # 設計ドキュメント（plan/spec/todo/knowledge）
├── .github/workflows/     # CI/CD（deploy.yml）— 現在 secret 未設定で未稼働
├── Dockerfile             # コンテナイメージ定義
├── requirements-dev.txt   # 開発用依存
├── pytest.ini             # pytest 設定
└── trust-policy.json      # IAM 信頼ポリシー（Lambda実行ロール用）
```

## ローカル開発・デプロイ
### テスト実行
```bash
python -m pytest tests/ -v
```

### Lambda 手動デプロイ（同期版・暫定）
```bash
docker build --platform linux/amd64 -t mosaic-app:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker tag mosaic-app:latest <account>.dkr.ecr.us-east-1.amazonaws.com/mosaic-app:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/mosaic-app:latest
aws lambda update-function-code --function-name mosaic-app --image-uri <account>.dkr.ecr.us-east-1.amazonaws.com/mosaic-app:latest
```
※ Phase 2 移行後は `sam deploy` で一発になる予定。

## 環境変数（Lambda）
| 変数名 | 説明 |
|---|---|
| `S3_BUCKET_NAME` | 画像保存用 S3 バケット |
| `REKOGNITION_COLLECTION_ID` | 登録顔のコレクション ID |
| `MOSAIC_MODE` | `all`（全員モザイク）or `exclude`（登録外をモザイク） |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot の token |
| `LINE_CHANNEL_SECRET` | LINE Bot の secret（webhook 署名検証用） |

実値は `~/.secrets/mosaic-app.env` に保存（このリポジトリには絶対に含めない）。

## 主要な設定値（コード内ハードコード）
- `face_limit`: 20（`image_handler.py:56`、20人超は全員モザイク）
- `similarity_threshold`: 50.0%（`image_handler.py:57`、登録判定の閾値）
- `mosaic_strength`: 20（`mosaic_processor.py`、モザイクの粒度）

## 関連リソースの確認方法
```bash
# Lambda 関数の状態
aws lambda get-function-configuration --function-name mosaic-app --region us-east-1

# API Gateway のステージ・URL
aws apigateway get-stages --rest-api-id <id> --region us-east-1

# 直近のログ
aws logs describe-log-streams --log-group-name /aws/lambda/mosaic-app --region us-east-1 --order-by LastEventTime --descending --max-items 5
```
