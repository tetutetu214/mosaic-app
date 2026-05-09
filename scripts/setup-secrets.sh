#!/usr/bin/env bash
# LINE のシークレット2本を SSM Parameter Store (SecureString) に投入する
# 初回または値の更新時にだけ実行する

set -euo pipefail

source "$HOME/.secrets/mosaic-app.env"

aws ssm put-parameter \
  --name "$LINE_CHANNEL_SECRET_PARAM" \
  --value "$LINE_CHANNEL_SECRET" \
  --type "SecureString" \
  --overwrite \
  --region us-east-1

aws ssm put-parameter \
  --name "$LINE_CHANNEL_ACCESS_TOKEN_PARAM" \
  --value "$LINE_CHANNEL_ACCESS_TOKEN" \
  --type "SecureString" \
  --overwrite \
  --region us-east-1

echo "secrets updated."
