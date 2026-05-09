# todo

## 進行中
なし

## 残課題
なし（Phase 2 完了 2026-05-09）

## Phase 2-A: spec.md 作成（完了 2026-05-09）
- [x] 第1章 ディレクトリ構造とビルド構成
- [x] 第2章 CDK スタック全体構造
- [x] 第3章 handler Lambda 仕様
- [x] 第4章 processor Lambda 仕様
- [x] 第5章 SQS / DLQ 仕様
- [x] 第6章 環境変数一覧
- [x] 第7章 IAM ポリシー最小権限設計
- [x] 第8章 テスト戦略
- [x] てつてつによる章ごとレビュー
- [x] 実装着手前の理解度テスト（CLAUDE.md ハーネス規約）— 2026-05-09 全問正解

## Phase 2-B: 実装（完了 2026-05-09）
- [x] AWS CDK のローカル環境確認（`cdk --version` 2.1121.0 / venv 構築）
- [x] shared/ 共通ユーティリティ実装 + テスト 11件
- [x] handler Lambda 実装 + テスト 10件
- [x] processor Lambda 実装（既存ロジック移植）+ テスト 9件
- [x] CDK プロジェクト雛形作成（cdk/app.py、stacks/mosaic_stack.py、cdk.json、requirements.txt）
- [x] CDK スナップショットテスト 9件
- [x] `cdk synth` で CFn テンプレート生成を確認（エラーなし）
- [x] `cdk diff` で既存スタックとの差分確認

## Phase 2-C: デプロイ・検証（完了 2026-05-09）
- [x] `cdk bootstrap` 実行確認
- [x] `cdk deploy` で初回デプロイ（`MosaicAppV2-HandlerFunction*` / `MosaicAppV2-ProcessorFunction*`）
- [x] LINE Webhook URL を新エンドポイントに切替
- [x] 動作検証（CloudWatch Logs に invocation 履歴あり）
- [x] ログ・メトリクス監視

## Phase 2-D: 旧構成の停止（完了 2026-05-09）
- [x] 旧 mosaic-app Lambda 削除（CDK スタック外なので個別削除）
- [x] 旧 API Gateway `mosaic-app-api` (`1w1zu1vfnb`) 削除
- [x] 旧 ECR リポジトリ `mosaic-app` 削除（イメージ含む `--force`）
- [x] 旧 CloudWatch Log Group `/aws/lambda/mosaic-app` 削除
- [x] 旧 IAM Role `lambda-execution-role` 削除（attached policies の detach 込み）
- [x] CI/CD（`.github/workflows/deploy.yml`）削除（v1 専用で一度も発火していなかったため）
- [x] v1 旧コード（`lambda-function/`、ルート `Dockerfile`、`trust-policy.json`、旧 `tests/test_*.py`）削除
- [x] README.md を v2 構成に全面刷新
- [x] `docs/architecture.drawio` を追加

### 残存（共有・温存）
- S3 バケット（画像保存・登録顔元）
- Rekognition コレクション `mosaic-app-faces`（登録顔データ）
- SSM Parameter Store の `/mosaic-app/line-channel-*`

## 完了済（Phase 1相当・2026-05-07 セッション）
- [x] mosaic-app の現状調査（Lambda・ECR・API Gatewayの構成把握）
- [x] 5/3 の Dockerfile 修正分を Lambda にデプロイ（手動）
- [x] README.md に「複数登録時の挙動」を追記
- [x] LINE Webhook 不通の原因切り分け（手前のLINE→API Gateway 経路で配信停止）
