# todo

## 進行中
なし

## 次にやること（Phase 2-A: spec.md 作成）
- [ ] docs/spec.md を新規作成
  - SAM テンプレート（template.yaml）の完全な構造設計
  - handler Lambda の擬似コード（webhook signature 検証 + SQS送信）
  - processor Lambda の擬似コード（既存ロジック + push API 送信）
  - 環境変数の一覧（新規追加: SQS_QUEUE_URL）
  - IAM ポリシードキュメントの最小権限設計
- [ ] 設計内容のレビューを受ける（てつてつ）

## Phase 2-B: 実装
- [ ] SAM CLI のローカルインストール確認
- [ ] template.yaml 作成
- [ ] handler Lambda コード（webhook受信専用）の実装
- [ ] processor Lambda コード（画像処理専用）の実装
- [ ] テストコード追加（handler / processor 個別）
- [ ] sam build でローカル検証

## Phase 2-C: デプロイ・検証
- [ ] sam deploy --guided で初回デプロイ
- [ ] LINE Webhook URL を新エンドポイントに切替
- [ ] 動作検証（plan.md の検証計画 参照）
- [ ] ログ・メトリクス監視

## Phase 2-D: 旧構成の停止
- [ ] 旧 mosaic-app Lambda の reserved concurrency = 0 で実質無効化
- [ ] 1週間問題なければ旧 API Gateway, 旧 Lambda 削除
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
