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
- IaC: AWS CDK (Python)（2026-05-08 に SAM から再選定）
- キュー: SQS Standard
- Lambda 配置: コンテナ Image 継続
- 返信: Push API（reply token は使わない）

### 並行運用方式
既存の mosaic-app Lambda・API Gateway は残したまま、`mosaic-app-v2` という別スタックで新構成を構築。LINE Webhook URL の切替で本番化、戻すのも URL 戻すだけ。

## 2026-05-08 セッションでの決定

### IaC を SAM → CDK (Python) に再選定

plan.md 初稿（2026-05-07）では IaC を AWS SAM としていたが、本日のセッションで以下の理由で CDK (Python) に切り替えた。

**切り替えの根拠**:
- CLAUDE.md の言語選定方針が「Python 優先」。SAM は YAML で完結するが、Python ではない
- てつてつは別プロジェクト（chicken-rag）で CDK 運用経験があり、SAM を新たに学ぶより既存スキルを活かす方が学習効率が高い
- 同じ Lambda + SQS 構成を SAM と CDK で書き比べた結果、行数は CDK の方が短い場合もあり「SAM の方が短い」というメリットが本構成では成立しなかった
- L2 コンストラクトが必要 IAM 権限を最小権限で自動付与するため、複数 Lambda + SQS のような構成では安全性の面でも CDK が有利

**初回 plan.md で SAM を選んでしまった原因**:
- 「Lambda + API Gateway + SQS のサーバーレスで SAM」という一般論に引っ張られ、てつてつのスキルセットや言語選定方針を選定根拠に組み込まなかった
- 教訓: 技術選定では「一般論」だけでなく「ユーザー固有の前提条件（言語、既存経験、運用方針）」を必ず根拠に入れる

**ECR の扱いの変化**:
- SAM 時代は `mosaic-app-v2-handler` / `mosaic-app-v2-processor` のように独立 ECR リポジトリを作る前提だった
- CDK の `DockerImageAsset` を使うと、`cdk bootstrap` で作成される共有 ECR リポジトリ（`cdk-hnb659fds-container-assets-{account}-{region}`）に自動 push される
- リポジトリ名指定の制御を失う代わりに、digest ベースのタグ管理を CDK が自動でやってくれる

## 学習済み概念（理解度テスト合格分）

次回以降のセッションでこれらをスキップ判定に使う。

### 2026-05-07
- **Lambda update-function-code の挙動**: イメージ参照を差し替える。既存実行環境は旧コードで動き続け、cold start から新コードに切り替わる
- **Lambda 更新中の動作**: 新旧が並存して徐々に切替（ローリング）。健全なイメージならダウンタイム原則ゼロ
- **コンテナ Lambda のロールバック**: 直前のイメージ digest を `update-function-code --image-uri` で再指定（タグ削除では戻らない）

### 2026-05-09（Phase 2-C デプロイ直前テスト合格）
- **CDK スタックが CFn 上に展開する実リソース数の感覚**: コード上 9 コンストラクトでも、CDK が IAM Role/Policy・API Gateway 子リソース（Account/Deployment/Stage/Resource/Method）・Lambda Permission を自動展開するため、実際の CFn リソースは約19個になる。`cdk diff` の Resources セクションで確認できる
- **並行運用（Blue/Green 相当）方式の安全性**: 新スタックを旧スタックの「横」に作り、LINE Webhook URL の切替で本番化する方式では、既存 Lambda・API Gateway は CDK 管轄外で触られない。S3・Rekognition データも維持される。ロールバックは Webhook URL を戻すだけで完了
- **ロールバック手順の優先順位**: 並行運用ならまず「Webhook URL を旧に戻す」が最安全・最速。`cdk destroy` は重く、SSM 削除や Lambda 無効化は副作用が大きい。リカバリー後は再切替で復活可能なので、新スタックを温存しておく

### 2026-05-09（Phase 2-A spec.md 完成・実装着手前テスト合格）
- **SQS visibility_timeout を関数 timeout の6倍に設定する理由**: 受信中の Lambda が処理中に他の Lambda が同じメッセージを取って二重実行するのを防ぐため。SQS は at-least-once delivery で、visibility timeout が短すぎると同一メッセージが複数 Lambda に再配送される
- **reply token を SQS に乗せない理由**: reply token は受信から1分しか有効でない。SQS で非同期化すると processor が取り出した時点で期限切れの可能性があるため、Push API に統一する
- **processor の reserved_concurrent_executions=5 の根拠**: Rekognition のレート制限と LINE Push API の通数枠が外部の上限。SQS は数千 TPS でも捌けるが、それに引きずられて processor が無限スケールするとスロットリング・通数オーバーが起きる。Lambda 側の予約並列度で抑える

## 2026-05-09 セッションでの Phase 2-B 実装で得た知見

### CDK の DockerImageAsset で directory にプロジェクトルートを指定するときの罠

`from_image_asset(directory=PROJECT_ROOT, file="handler/Dockerfile")` のようにビルドコンテキストをプロジェクトルートにすると、shared/ などの兄弟ディレクトリを Dockerfile から `COPY shared/` できる利点がある。

しかし **exclude を指定しないと cdk synth が ENAMETOOLONG で失敗する**。

理由: CDK は asset を `cdk/cdk.out/asset.{hash}/` にコピーする。プロジェクトルートには `cdk/` がそのまま含まれているので、コピー対象に `cdk/cdk.out/asset.{hash}/cdk/cdk.out/asset.{hash}/...` という再帰ネストが発生し、ファイル名が長くなりすぎてOSエラー。

**対策**: `from_image_asset(exclude=[...])` で次のような大物・自己参照系のパスを除外する。
- `cdk/cdk.out`、`cdk/.cdk.staging`、`cdk` 自体
- `.venv`（数百MB）
- `tests`、`docs`、`lambda-function`、`scripts`（Lambda ランタイムで不要）
- `.git`、`node_modules`、`**/__pycache__`、`.pytest_cache`

教訓: DockerImageAsset でプロジェクトルートを context に使うときは、`exclude` または `.dockerignore` での除外を **必ず** セットで考える。spec 段階でも「除外パスの設計」をチェック項目に入れるべき。

### pytest と sys.path 解決の罠（pytest 9.x）

- pytest.ini のヘッダーは `[pytest]`（`[tool:pytest]` は setup.cfg / tox.ini 用、pytest 8+ で pytest.ini では機能しない設定がある）
- `tests/<sub>/__init__.py` を作ると、pytest が tests/ 配下を「パッケージ」として扱い、プロジェクトルートを sys.path に追加してくれない場合がある（既存 `tests/` 直下に `__init__.py` がない構造ではこれが原因で ModuleNotFoundError）
- 対策: ルートに `conftest.py` を置き、`sys.path.insert(0, str(Path(__file__).parent))` で明示。tests/<sub>/ には `__init__.py` を作らない

### Lambda コンテナの内部モジュールを pytest から import する方法

Lambda runtime は `LAMBDA_TASK_ROOT` を sys.path に含めるので、`processor/app.py` が `from mosaic_processor import detect_faces` のように **同ディレクトリ兄弟モジュール** を直接 import できる。

ローカルテストで同じ振る舞いを再現するには、`tests/processor/conftest.py` で `sys.path.insert(0, str(PROJECT_ROOT / "processor"))` を実行する。これで本番ランタイムと同じ import 解決が走り、コードを変更せずにテストできる。
