# mosaic-app Phase2 計画書

## 背景と問題分析

### 現状アーキテクチャ（同期処理）
```
LINE → API Gateway → Lambda(mosaic-app)
                       ├ 画像DL（LINE API）
                       ├ S3 upload
                       ├ Rekognition 顔検出
                       ├ 個別照合（最大20回ループ）
                       ├ PIL でモザイク処理
                       ├ S3 upload
                       └ reply token で画像返信
```
Lambda タイムアウト 30秒、メモリ 512MB の同期処理。reply token で返信。

### 確認された問題
2026-05-07 のセッションで以下が判明した。

- 5/7 12:38 JST に写真を送ったが API Gateway にリクエストが到達しなかった（呼び出し0件）
- 4/17 から 5/7 22:48 まで Lambda 実行履歴が空白（4/17 を最後に webhook が止まっていた）
- デプロイ直後に動作確認したところ正常応答した（22:48 JST 時点でログ確認済み）

### 根本原因
LINE Messaging API の公式仕様では「webhook 受信後 2秒以内に HTTP 2xx を返さないと request_timeout エラー扱い」となる（certified provider 基準）。LINE は Webhook が連続でタイムアウト・エラーを返すと配信を一時停止する挙動があり、過去の Lambda タイムアウトやエラーの累積が原因で webhook 配信が止まっていた可能性が高い。

LINE 公式も「webhook イベントは非同期処理を推奨」と明言しており、現状の同期アーキテクチャは LINE Bot のベストプラクティスから外れている。

参考: [LINE Webhook check error statistics](https://developers.line.biz/en/docs/messaging-api/check-webhook-error-statistics/)

## ゴール

mosaic-app の「ときどき写真を送っても反応しない」問題を、以下の構造で恒久的に解決する。

1. LINE webhook には 2秒以内に必ず 2xx を返す（同期 Lambda の処理時間に依存しない）
2. 画像処理は時間制約から解放し、必要なだけ時間をかけられるようにする
3. 失敗時に自動リトライ・DLQ で取りこぼしをなくす
4. IaC で構成を再現可能にする（CI/CD整備の前提）

## 採用アーキテクチャ（非同期処理）

```
LINE → API Gateway → handler Lambda（受信・即200）
                       ├ webhook signature 検証
                       ├ reply token で「処理を開始しました」をテキスト即返答
                       ├ SQS にイベント（userId, messageId など）をエンキュー
                       └ 200 OK 即返却（< 1秒）

                     SQS Standard Queue
                       ↓ event source mapping
                     processor Lambda（重処理）
                       ├ 画像DL（LINE API）
                       ├ S3 upload
                       ├ Rekognition 顔検出 + 個別照合
                       ├ PIL モザイク処理
                       ├ S3 upload（出力画像）
                       └ Push API で処理結果の画像をユーザーに送信

                     DLQ（Dead Letter Queue）
                       └ 5回リトライ後の失敗メッセージを保管（後で調査用）
```

## 技術選定（理由付き）

### IaC: AWS CDK (Python)
**選定理由**: 既存プロジェクト（chicken-rag）で CDK の運用経験があり、ナレッジを再利用できる。CLAUDE.md の言語選定方針（Python 優先）とも合致し、新たに YAML/別言語を学ぶ必要がない。L2 コンストラクトが IAM 権限を最小権限で自動付与する仕組みも、本構成のように複数 Lambda + SQS が絡む場面で安全性が高い。CDK の `DockerImageAsset` がイメージの digest 管理を自動化するため、Container Image 更新時の CFn 検出問題も透過的に扱える。

**代替案との比較**:
- **SAM**: YAML 完結で最初の学習が軽い利点はあるが、CDK 経験がある前提では学習負担がむしろ増える方向。Lambda + SQS 程度の構成では行数も大差ない（むしろ CDK の方が短い）
- **Terraform**: マルチクラウド対応の汎用性は高いが、Python ベースでない・AWS 純正でないため、本プロジェクトでは優位性なし
- **CFn 直書き**: IAM Role や EventSourceMapping を手書きする必要があり、行数が膨らむ

※ 2026-05-07 の plan 初稿時点では SAM を選定していたが、2026-05-08 のセッションで「てつてつは Python 優先かつ CDK 経験あり」という前提を踏まえ CDK に再選定し直した。経緯は knowledge.md 参照。

### SQS: Standard
**選定理由**: webhook イベントは順序保証不要で、重複排除も processor 側で冪等にすれば対応可能。Standard は TPS 制限なし、月間 100万メッセージまで無料。

**代替案との比較**:
- **FIFO**: 順序保証・重複排除に魅力があるが、TPS 制限（300/秒）と料金が高くなる。今回不要

### Lambda 配置: コンテナ Image 継承
**選定理由**: 既存 mosaic-app は PIL・Pillow 依存でレイヤー構成が複雑。Container Image なら `Dockerfile` 1ファイルで再現可能。既に ECR リポジトリ・Lambda 関数が Container 構成で動いている実績あり。

**代替案との比較**:
- **Zip + Lambda Layer**: PIL の依存を Layer に切り出す手があるが、Container と同等の利便性を得るには工夫が要る。既存資産を活かす方が早い

### LINE 返信: Push API
**選定理由**: 非同期化により reply token（受信から1分有効）が間に合わない。Push API は時間制約なし、月 200通まで無料（Communication Plan）。個人ユース想定なら無料枠で十分。

**代替案との比較**:
- **reply token のみ**: 非同期化と矛盾するので採用不可
- **Multicast / Broadcast**: 1対1のbotには不要

参考: [LINE Messaging API pricing](https://developers.line.biz/en/docs/messaging-api/pricing/)

### IAM: 最小権限の原則
- handler Lambda の実行ロール: `sqs:SendMessage`（自分のキューだけ）, CloudWatch Logs 標準権限
- processor Lambda の実行ロール: `AWSLambdaSQSQueueExecutionRole`（SQS receive/delete）, `s3:GetObject/PutObject`（バケット範囲限定）, `rekognition:SearchFacesByImage` `rekognition:DetectFaces`（コレクション範囲限定）, CloudWatch Logs 標準権限
- 信頼ポリシー: `lambda.amazonaws.com` のみ

## SQS / Lambda パラメータ設計

AWS 公式ベストプラクティスに従う。

| 項目 | 値 | 理由 |
|---|---|---|
| processor Lambda timeout | 180秒（3分） | 重い写真でも余裕あり。15分まで延ばせるが過剰 |
| processor Lambda memory | 1024 MB | 512MB ではメモリ・CPU不足の懸念。1024MB で CPU 配分が上がり処理時間も短縮 |
| SQS visibility timeout | 1080秒（18分） | 関数 timeout の **6倍以上** がベストプラクティス（180秒×6=1080秒） |
| SQS message retention | 4日 | デフォルト維持 |
| SQS event source batch size | 1 | 画像処理1件ずつ独立。バッチ失敗で巻き込み事故を避ける |
| DLQ maxReceiveCount | 5 | 公式推奨「5以上」。一時的なRekognitionスロットリングを乗り越える余地 |
| handler Lambda timeout | 5秒 | 即200を返すだけなので短く。LINEの2秒制限に余裕を持たせる |
| handler Lambda memory | 256 MB | 軽量処理 |
| handler 同時実行数 | 既定（無制限） | LINE webhook の急峻なバーストに対応 |
| processor 同時実行数 | 5（reserved concurrency） | Rekognition のレート制限・自分のLINE Push API 通数の制御 |

参考: [Using Lambda with Amazon SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)

## 移行計画

### 並行運用方式（Blue/Green相当）
既存の `mosaic-app` Lambda・API Gatewayは**残したまま**、新しい SAM スタックを別名で構築する。LINE Webhook URL の切替で本番化する。

- 新スタック名: `mosaic-app-v2`（新 API Gateway, 新 Lambda 2つ, 新 SQS, 新 DLQ）
- 既存リソース: 触らない（緊急時のロールバック先として温存）
- 切替操作: LINE Developers コンソールで Webhook URL を新エンドポイントに書き換えるだけ
- 切戻操作: Webhook URL を旧エンドポイントに戻すだけ

### S3 / Rekognition コレクションの扱い
既存の S3 バケットと Rekognition コレクションはそのまま再利用する。新スタックの IAM ロールにアクセス権限を付与するだけ。

理由: バケットや顔データは「状態」を持つリソースなので、移行時に作り直すと既存ユーザーの登録顔データが消える。再利用が安全。

### 段階的移行手順（次セッション以降）

1. CDK プロジェクト雛形作成（`cdk/` ディレクトリに `app.py`・`stacks/`・`cdk.json`）
2. handler Lambda コード作成（`handler/` ディレクトリに分離）
3. processor Lambda コード作成（既存 lambda-function/ をベースに修正）
4. ローカル `cdk synth` で CFn テンプレートを生成して内容確認、`cdk diff` で既存スタックとの差分確認
5. `cdk bootstrap`（未実施なら）→ `cdk deploy` でデプロイ
6. テスト用LINEチャネル（あれば）で動作確認、なければ本番LINE Webhook URL を一時的に切替
7. 1〜2日様子見、ログ・メトリクス確認
8. 問題なければ既存 Lambda の停止（reserved concurrency = 0 で実質無効化）
9. 1週間以上問題なければ既存リソース削除（`cdk destroy` ではなく旧 Lambda・旧 API Gateway を個別に削除する。新スタックには影響しない）

## リスクと対応

| リスク | 影響 | 対応 |
|---|---|---|
| Push API 200通/月の枠超過 | 処理結果が返せなくなる | 通数監視、必要なら有料プランに切替 |
| LINE 画像取得 API の有効期限（メッセージID 1週間） | 古いメッセージが処理できない | SQS のretentionは4日なので問題なし。DLQ送りになった画像は手動再処理時に注意 |
| Rekognition のレート制限 | スロットリング | processor の reserved concurrency を5に絞る、DLQ から再処理 |
| webhook signature 未検証 | なりすまし送信を受け付ける | handler Lambda で `X-Line-Signature` を必ず検証、不一致なら403 |
| Container Image 更新が CFn 自動検出されない | デプロイしても新コードが反映されないリスク | CDK の `DockerImageAsset` は build 時にコンテンツハッシュ（SHA256）を計算して image URI に埋め込むため、コード変更があれば自動で別イメージとして push され Lambda が更新される |

## コスト見積（個人ユース月100リクエスト想定）

| サービス | 内訳 | 月額（USD） |
|---|---|---|
| Lambda（handler） | 100回 × 0.5秒 × 256MB | 無料枠内（< $0.01） |
| Lambda（processor） | 100回 × 60秒 × 1024MB | 無料枠内（< $0.10） |
| API Gateway | REST 100リクエスト | 無料枠内（< $0.01） |
| SQS | Standard 100メッセージ | 無料枠内 |
| ECR | コンテナイメージ保存 1GB相当 | $0.10/月 |
| S3 | 入出力画像保存 1GB相当 | $0.023/月 |
| Rekognition | DetectFaces + SearchFacesByImage 各100回 | $0.30/月 |

合計: 月額 **$0.5未満**。既存 mosaic-app と大差なし。

参考: 価格は AWS 公式 Pricing API で次セッション開始時にもう一度確認する。

## 検証計画

実装後の検証項目:
1. **基本動作**: 写真送信 → 数十秒以内に画像返信が来る
2. **複数登録**: 2人以上の登録で全員除外される
3. **20人超**: 全員モザイク処理になる
4. **エラー時のDLQ送り**: 故意に壊れた画像を送って5回リトライ後DLQに入ることを確認
5. **負荷**: 連続10枚送信しても全件返信される
6. **LINE タイムアウト**: handler Lambda の Duration が 1秒以下に収まる
7. **失敗時の通知**: DLQ にメッセージが入ったら CloudWatch Alarms で通知（任意・余裕があれば）

## マイルストーン

| フェーズ | 内容 | 想定セッション数 |
|---|---|---|
| Phase 2-A | docs整備・CDKスタック設計（spec.md） | 1セッション |
| Phase 2-B | handler / processor Lambda コード実装 | 1〜2セッション |
| Phase 2-C | sam deploy・動作検証・LINE Webhook 切替 | 1セッション |
| Phase 2-D | 既存リソース停止・削除・CI/CD更新 | 1セッション |

## 参考資料

- [Process events asynchronously with API Gateway and Lambda](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/process-events-asynchronously-with-amazon-api-gateway-and-aws-lambda.html)
- [Using Lambda with Amazon SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [AWS CDK v2 Python API Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
- [AWS CDK aws-lambda DockerImageFunction](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/DockerImageFunction.html)
- [AWS CDK aws-lambda-event-sources SqsEventSource](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda_event_sources/SqsEventSource.html)
- [LINE Messaging API webhook receiving](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
- [LINE Messaging API pricing](https://developers.line.biz/en/docs/messaging-api/pricing/)
