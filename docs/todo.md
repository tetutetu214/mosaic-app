# todo

## 進行中
なし

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

## Phase 2-B: 実装
- [ ] AWS CDK のローカル環境確認（`cdk --version` / Python venv）
- [ ] CDK プロジェクト雛形作成（`cdk/` 配下に app.py / stacks / cdk.json / requirements.txt）
- [ ] handler Lambda コード（webhook受信専用）の実装
- [ ] processor Lambda コード（画像処理専用）の実装
- [ ] shared/ ディレクトリの共通ユーティリティ実装
- [ ] テストコード追加（handler / processor / shared 個別）
- [ ] `cdk synth` で CFn テンプレートを生成して内容確認
- [ ] `cdk diff` で既存スタックとの差分確認

## Phase 2-C: デプロイ・検証
- [ ] `cdk bootstrap` 実行確認（同アカウント・同リージョンで未実施なら）
- [ ] `cdk deploy` で初回デプロイ
- [ ] LINE Webhook URL を新エンドポイントに切替
- [ ] 動作検証（plan.md の検証計画 参照）
- [ ] ログ・メトリクス監視

## Phase 2-D: 旧構成の停止
- [ ] 旧 mosaic-app Lambda の reserved concurrency = 0 で実質無効化
- [ ] 1週間問題なければ旧 API Gateway, 旧 Lambda 削除（CDK スタック外なので個別削除）
- [ ] CI/CD（.github/workflows/deploy.yml）を新スタック用に更新

## 既存課題（Phase 2 と並行・後追い可）
- [ ] GitHub Actions の AWS_ROLE_ARN secret 設定（OIDC連携用 IAM Role 含む）。現状CI/CDが一度も発火していない
- [ ] Secret Scanning（Push Protection）の有効化確認
- [ ] AWS リソース（S3バケット名・Rekognition コレクションID）の控えを ~/.secrets/ に保存

## 完了済（Phase 1相当・2026-05-07 セッション）
- [x] mosaic-app の現状調査（Lambda・ECR・API Gatewayの構成把握）
- [x] 5/3 の Dockerfile 修正分を Lambda にデプロイ（手動）
- [x] README.md に「複数登録時の挙動」を追記
- [x] LINE Webhook 不通の原因切り分け（手前のLINE→API Gateway 経路で配信停止）
