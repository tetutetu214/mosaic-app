# knowledge — 開発知見・決定事項

## アーキテクチャに関する知見

### LINE Webhook の応答タイムアウト要件
LINE Messaging API は webhook 受信後 **2秒以内に HTTP 2xx を返さない** と request_timeout エラー扱いになる（certified provider 基準）。タイムアウトやエラーが連続すると LINE 側で webhook 配信を一時停止する挙動がある。

→ Lambda での画像処理を同期で行うと、コールドスタートや重い写真処理で2秒制限を突破して webhook が止まる原因になる。**非同期処理がLINE公式の推奨**。

参考: <https://developers.line.biz/en/docs/messaging-api/check-webhook-error-statistics/>

### LINE Push API の通数制限
- Communication Plan（無料）: 200通/月
- Light Plan: 5,000通/月
- Standard Plan: 30,000通/月

カウントは「送信先人数」単位。個人ユース（1対1のbot）なら無料枠で十分。

参考: <https://developers.line.biz/en/docs/messaging-api/pricing/>

### SQS event source mapping のベストプラクティス（AWS公式）
- SQS の visibility timeout は **関数 timeout の 6倍以上**
- DLQ の `maxReceiveCount` は **5以上**
- Partial batch response 推奨
- IAM 実行ロールには **AWSLambdaSQSQueueExecutionRole** マネージドポリシー
- Lambda 関数と SQS は同一リージョン必須

参考: <https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html>

### Lambda コンテナイメージのデプロイ
- `AWS::Serverless::Function` で `PackageType: Image` 指定
- イメージ更新時は SAM が自動で digest を取得して CFn テンプレートに埋めるので CFn 自動検出される
- 一方、**ECR の同じタグ（`latest`等）に push 直しただけでは CFn からの更新は検出されない**。CI/CD では git SHA タグを毎回別タグにすること

## 2026-05-07 セッションでの調査結果

### 当日の事実関係（時刻はすべて JST）
- 12:38: 写真を送ったが反応なし → API Gateway 呼び出し0件、Lambda呼び出し0件で確定
- 4/17 〜 5/7 22:48: Lambda 実行履歴の空白期間（4/17 を最後に webhook が止まっていた）
- 22:45: Dockerfile パス修正分を手動でLambdaにデプロイ
- 22:48: デプロイ後の動作確認で正常応答（7顔の画像処理ログを確認）
- 23:12: 再送実施 → API Gateway 1件届いたが画像処理ログなし、Duration 3.5秒、Memory 105MB のみ（画像メッセージとして処理されなかった or LINE側の verify ping 等の可能性）

### 推定原因
過去の Lambda タイムアウト（30秒設定）・エラー累積で LINE 側が webhook 配信を一時停止した。デプロイ・LINE側の自動再有効化試行・てつてつ側の操作いずれかで部分的に復活した可能性。

### Lambda 過去のエラーログ（2025年）
直近では発生していないが、2025年に以下のエラー履歴あり:
- 環境変数不足（S3_BUCKET_NAME 等）
- Rekognition コレクション不存在
- Pythonの構文エラー（`invalid syntax`）
- LINE API 401 Unauthorized

これらの蓄積が webhook 自動停止の遠因になった可能性。

## 決定事項

### Phase2 の方向性
受信用 Lambda と画像処理用 Lambda を分離し、SQS で非同期化する（plan.md 参照）。並行運用方式で安全に切替する。

### 採用技術
- IaC: AWS SAM
- キュー: SQS Standard
- Lambda 配置: コンテナ Image 継続
- 返信: Push API（reply token は使わない）

### 並行運用方式
既存の mosaic-app Lambda・API Gateway は残したまま、`mosaic-app-v2` という別スタックで新構成を構築。LINE Webhook URL の切替で本番化、戻すのも URL 戻すだけ。

## 学習済み概念（理解度テスト合格分）

次回以降のセッションでこれらをスキップ判定に使う。

### 2026-05-07
- **Lambda update-function-code の挙動**: イメージ参照を差し替える。既存実行環境は旧コードで動き続け、cold start から新コードに切り替わる
- **Lambda 更新中の動作**: 新旧が並存して徐々に切替（ローリング）。健全なイメージならダウンタイム原則ゼロ
- **コンテナ Lambda のロールバック**: 直前のイメージ digest を `update-function-code --image-uri` で再指定（タグ削除では戻らない）
