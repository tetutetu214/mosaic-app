#!/usr/bin/env bash
# mosaic-app v2 を CDK でデプロイする
# 事前に scripts/setup-secrets.sh を実行して SSM Parameter を設定しておくこと

set -euo pipefail

source "$HOME/.secrets/mosaic-app.env"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# venv を有効化（aws_cdk ライブラリと CDK CLI から呼ばれる python の整合のため）
source "$PROJECT_ROOT/.venv/bin/activate"

cd "$PROJECT_ROOT/cdk"

cdk deploy MosaicAppV2 \
  -c s3_bucket_name="$S3_BUCKET_NAME" \
  -c rekognition_collection_id="$REKOGNITION_COLLECTION_ID" \
  -c line_channel_secret_param="$LINE_CHANNEL_SECRET_PARAM" \
  -c line_channel_access_token_param="$LINE_CHANNEL_ACCESS_TOKEN_PARAM" \
  --require-approval never
