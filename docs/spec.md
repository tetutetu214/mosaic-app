# mosaic-app Phase2 仕様書

本書は `docs/plan.md` で確定した Phase 2 計画を、実装に落とすための具体仕様としてまとめたもの。
CDK スタック構造・各 Lambda の擬似コード・IAM 最小権限・テスト戦略までを章ごとに定義する。

IaC は **AWS CDK (Python)**。2026-05-08 のセッションで SAM から再選定し直した経緯は `knowledge.md` 参照。

---

## 第1章 ディレクトリ構造とビルド構成

### 1.1 ディレクトリ構造

```
mosaic-app/
├── cdk/                        # CDK プロジェクト（新規）
│   ├── app.py                  # CDK アプリケーションエントリポイント
│   ├── stacks/
│   │   ├── __init__.py
│   │   └── mosaic_stack.py     # メインスタック定義
│   ├── cdk.json                # CDK 設定（context、feature flags）
│   ├── requirements.txt        # aws-cdk-lib, constructs
│   └── tests/                  # CDK スナップショット/単体テスト
│       └── test_mosaic_stack.py
├── handler/                    # 受信用 Lambda（新規）
│   ├── Dockerfile
│   ├── app.py                  # エントリポイント
│   └── requirements.txt        # boto3, requests のみ
├── processor/                  # 画像処理用 Lambda（新規）
│   ├── Dockerfile
│   ├── app.py                  # エントリポイント
│   ├── image_handler.py        # 既存 lambda-function/ から移植
│   ├── mosaic_processor.py     # 既存 lambda-function/ から移植
│   └── requirements.txt        # Pillow, boto3, requests
├── shared/                     # handler/processor 共通コード（新規）
│   ├── __init__.py
│   ├── line_signature.py       # X-Line-Signature 検証
│   └── line_api.py             # reply / push API クライアント
├── tests/
│   ├── handler/                # 新規（Lambda コード単体テスト）
│   ├── processor/              # 既存テストを移行
│   └── shared/                 # 新規
├── lambda-function/            # ★旧 Phase 1 コード（Phase 2-D で削除予定、今は温存）
├── Dockerfile                  # ★旧 Phase 1 用（同上）
├── docs/
└── ...
```

設計上のポイント:

- `cdk/` を独立ディレクトリに切ることで、Lambda の実行コードと IaC コードが混ざらず、`cdk synth/deploy` の context もシンプルになる
- `shared/` を新設して、handler/processor で重複しがちな **LINE 署名検証** と **LINE API クライアント** を集約する。両 Lambda の Dockerfile から `COPY` される
- 旧 Phase 1 の `lambda-function/` と ルート `Dockerfile` は **削除しない**。並行運用方式（Blue/Green 相当）でロールバック可能性を残すため、Phase 2-D で安全宣言できるまで温存

### 1.2 CDK プロジェクトの最小構成

`cdk/cdk.json` の役割: CDK CLI が `cdk synth` 等を実行する際に、エントリポイント（`python3 app.py`）と context を読む設定ファイル。最小例:

```json
{
  "app": "python3 app.py",
  "context": {
    "@aws-cdk/aws-lambda:recognizeLayerVersion": true
  }
}
```

`cdk/app.py` の役割: スタッククラスをインスタンス化して `cdk synth` の対象に渡すエントリ。

```python
import aws_cdk as cdk
from stacks.mosaic_stack import MosaicStack

app = cdk.App()
MosaicStack(app, "MosaicAppV2",
    env=cdk.Environment(
        account=app.node.try_get_context("account") or None,
        region="us-east-1",
    ),
)
app.synth()
```

`cdk/requirements.txt` の役割: CDK ライブラリの依存解決。

```
aws-cdk-lib==2.x.x
constructs>=10.0.0,<11.0.0
```

### 1.3 ビルド構成（CDK DockerImageAsset）

handler / processor の Dockerfile を分けるため、**CDK の `DockerImageAsset` でビルドコンテキストをプロジェクトルートに揃える**。
理由: `shared/` を両 Lambda の Dockerfile から `COPY` するため、両者の親ディレクトリがコンテキストでないとパスが通らない。

CDK では `DockerImageCode.from_image_asset(directory=..., file=...)` で `directory` がコンテキスト、`file` が Dockerfile の相対パスになる。

```python
# stacks/mosaic_stack.py の抜粋（イメージ）
from aws_cdk import aws_lambda as _lambda
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

handler_fn = _lambda.DockerImageFunction(
    self, "HandlerFunction",
    code=_lambda.DockerImageCode.from_image_asset(
        directory=str(PROJECT_ROOT),
        file="handler/Dockerfile",
    ),
    timeout=Duration.seconds(5),
    memory_size=256,
)

processor_fn = _lambda.DockerImageFunction(
    self, "ProcessorFunction",
    code=_lambda.DockerImageCode.from_image_asset(
        directory=str(PROJECT_ROOT),
        file="processor/Dockerfile",
    ),
    timeout=Duration.seconds(180),
    memory_size=1024,
)
```

### 1.4 各 Dockerfile の設計

**handler/Dockerfile**

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

COPY handler/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY shared/ ${LAMBDA_TASK_ROOT}/shared/
COPY handler/app.py ${LAMBDA_TASK_ROOT}/

CMD ["app.lambda_handler"]
```

**processor/Dockerfile**

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

COPY processor/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY shared/ ${LAMBDA_TASK_ROOT}/shared/
COPY processor/ ${LAMBDA_TASK_ROOT}/

CMD ["app.lambda_handler"]
```

### 1.5 ECR リポジトリ

CDK の `DockerImageAsset` を使うと、`cdk bootstrap` で作成される **共有 ECR リポジトリ** に自動で push される。リポジトリ名は CDK が管理し、典型的には次のような名前になる。

- `cdk-hnb659fds-container-assets-{account-id}-{region}`

handler / processor は同じ共有リポジトリ内で **digest（SHA256ハッシュ）で区別** される。SAM 時代に検討していた `mosaic-app-v2-handler` / `mosaic-app-v2-processor` のような独立リポジトリは作成しない。

メリット:
- リポジトリ作成・命名・ライフサイクルポリシーを CDK が自動で管理
- イメージ更新時の digest 解決も自動

留意点:
- リポジトリ名を自分で決められないので、ECR コンソールで「どのアプリのイメージか」を識別しにくい場合がある（タグや description で補う）
- `cdk bootstrap` を一度実行する必要がある（同一アカウント・同一リージョンで未実施なら）

---

## 第2章 CDK スタック全体構造

### 2.1 スタックに含めるコンストラクト一覧

`MosaicStack` には次の9コンストラクトを定義する。これがスタック内で作成・管理される全リソース。

| # | Construct ID | コンストラクト型 | 役割 |
|---|---|---|---|
| 1 | `ProcessorDLQ` | `sqs.Queue` | 5回失敗した画像処理メッセージの保管庫 |
| 2 | `ProcessorQueue` | `sqs.Queue` | handler → processor のメインキュー（DLQ紐付け） |
| 3 | `HandlerFunction` | `lambda.DockerImageFunction` | LINE webhook 受信 Lambda |
| 4 | `ProcessorFunction` | `lambda.DockerImageFunction` | 画像処理 Lambda |
| 5 | `ProcessorEventSource` | `SqsEventSource` | ProcessorQueue → ProcessorFunction の紐付け |
| 6 | `MosaicApi` | `apigateway.RestApi` | LINE Webhook を受ける REST API |
| 7 | `WebhookResource` | `apigateway.Resource` | API Gateway のリソース（パス `/webhook`） |
| 8 | `WebhookMethod` | `apigateway.Method` | POST `/webhook` を HandlerFunction に Lambda Integration |
| 9 | `RegistrationStateTable` | `dynamodb.Table` | 「登録」モード中のユーザーIDを記録（24時間TTL付き） |

#### RegistrationStateTable のスキーマ

| 属性 | 型 | 説明 |
|---|---|---|
| `userId` (PK) | String | LINE userId |
| `registrationMode` | Boolean | `True` のとき登録モード中 |
| `ttl` | Number | エポック秒。24時間後に DynamoDB TTL で自動削除 |

設計判断:
- **PAY_PER_REQUEST**: 個人ユースで月数十回の RW しかない。プロビジョンド容量より安い
- **24時間 TTL**: 「登録」を打ったまま画像を送り忘れた時、いつまでも登録モードが残ると次の画像が誤って登録対象になる。これを防ぐため自動失効
- **RemovalPolicy.DESTROY**: ユーザーの一時状態のみ保持。`cdk destroy` で消えてOK。Rekognition コレクション本体（既存リソース）は別管理で影響なし

#### handler / processor と DynamoDB の関係

| 担当 | DynamoDB 操作 |
|---|---|
| handler | Read（モード確認）+ Write（モード ON/OFF） |
| processor | **アクセスしない** |

handler が SQS にメッセージを投げる時点で `mode: "register"` または `mode: "mosaic"` を埋め込み、processor は SQS メッセージの mode フィールドだけ見て分岐する。これにより processor は DynamoDB を知らずに済み、IAM 権限を最小化できる。

**スタックに含めない（既存リソース・CDK 外で管理）**:
- 既存 S3 バケット（画像保管用）
- 既存 Rekognition コレクション（登録顔データ）
- 既存 `mosaic-app` Lambda・既存 API Gateway（並行運用のため温存）

CloudWatch Log Group は `DockerImageFunction` が暗黙に作成する（`/aws/lambda/{関数名}`）ため、スタックには明示せず。

API Gateway は API名 `mosaic-app-v2-api`、ステージ名 `prod` とする。

### 2.2 既存リソース（S3・Rekognition）の参照方法

既存 S3 バケットと Rekognition コレクションは CDK スタックの管理外。本プロジェクトでは **context 経由 + デプロイヘルパースクリプト** 方式を採用する。

| 方法 | 内容 | 採否 |
|---|---|---|
| A. ARN ハードコード | スタック内に文字列リテラル | × 環境差し替え不可 |
| B. context 経由 | `cdk.json` または `cdk deploy -c name=value` | ○ 採用 |
| C. 環境変数で渡す | `os.environ.get(...)` を `app.py` で読む | × CDK 標準から外れる |
| D. CfnParameter | スタックの Parameter 化 | × 書き方が冗長 |

**実運用ルール**:
- AWS 識別情報（バケット名・コレクション名）は **リポジトリにコミットしない**（メモリ規約）
- `cdk.json` の `context` には実値を書かず、デプロイ時に `-c` で渡す
- デプロイ用ヘルパー `scripts/deploy.sh` を作って `~/.secrets/mosaic-app.env` を読み込み、`cdk deploy -c s3_bucket_name=$VAR ...` の形で起動する（chicken-rag・trip-road の `deploy_*.sh` と同じパターン）

### 2.3 スタッククラスのスケルトン

```python
# cdk/stacks/mosaic_stack.py
from pathlib import Path
from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_lambda as _lambda,
    aws_sqs as sqs,
    aws_apigateway as apigw,
    aws_lambda_event_sources as event_sources,
    aws_dynamodb as dynamodb,
)
from constructs import Construct

PROJECT_ROOT = Path(__file__).parent.parent.parent


class MosaicStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        s3_bucket_name: str,
        rekognition_collection_id: str,
        line_channel_access_token_param: str,  # SSM Parameter Store の名前
        line_channel_secret_param: str,        # 同上
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. DLQ（リテンション14日、SQS マネージド暗号化）
        dlq = sqs.Queue(self, "ProcessorDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # 2. メインキュー（DLQ紐付け、visibility は関数 timeout の6倍）
        queue = sqs.Queue(self, "ProcessorQueue",
            visibility_timeout=Duration.seconds(1080),
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=dlq),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # 9. 登録モード状態管理テーブル（24時間 TTL）
        table = dynamodb.Table(self, "RegistrationStateTable",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 3. handler Lambda（受信専用・軽量）
        handler_fn = _lambda.DockerImageFunction(self, "HandlerFunction",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=str(PROJECT_ROOT),
                file="handler/Dockerfile",
            ),
            timeout=Duration.seconds(5),
            memory_size=256,
            environment={
                "SQS_QUEUE_URL": queue.queue_url,
                "REGISTRATION_TABLE_NAME": table.table_name,
                "REKOGNITION_COLLECTION_ID": rekognition_collection_id,  # 「状態」コマンド用
                "LINE_CHANNEL_SECRET_PARAM": line_channel_secret_param,
                "LINE_CHANNEL_ACCESS_TOKEN_PARAM": line_channel_access_token_param,
            },
        )
        queue.grant_send_messages(handler_fn)
        table.grant_read_write_data(handler_fn)
        # SSM・Rekognition list_faces 権限は第7章で詳細定義

        # 4. processor Lambda（画像処理・重め）
        processor_fn = _lambda.DockerImageFunction(self, "ProcessorFunction",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=str(PROJECT_ROOT),
                file="processor/Dockerfile",
            ),
            timeout=Duration.seconds(180),
            memory_size=1024,
            reserved_concurrent_executions=5,
            environment={
                "S3_BUCKET_NAME": s3_bucket_name,
                "REKOGNITION_COLLECTION_ID": rekognition_collection_id,
                "MOSAIC_MODE": "exclude",
                "LINE_CHANNEL_ACCESS_TOKEN_PARAM": line_channel_access_token_param,
            },
        )
        queue.grant_consume_messages(processor_fn)
        # 既存 S3 / Rekognition / SSM への権限は第7章で詳細定義
        # processor には DynamoDB アクセス権限を付与しない（mode は SQS メッセージで通知）

        # 5. SQS → processor のイベントソース（partial batch response 対応）
        processor_fn.add_event_source(
            event_sources.SqsEventSource(queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )

        # 6-8. API Gateway
        api = apigw.RestApi(self, "MosaicApi",
            rest_api_name="mosaic-app-v2-api",
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )
        webhook = api.root.add_resource("webhook")
        webhook.add_method("POST", apigw.LambdaIntegration(handler_fn))
```

### 2.4 LINE シークレットの扱い

`CHANNEL_ACCESS_TOKEN` と `CHANNEL_SECRET` は機密。Lambda 環境変数に **平文で書かない**。

設計:
- **SSM Parameter Store の SecureString** に保存（無料枠で十分）
- スタックには **Parameter 名だけ** 渡す（例: `/mosaic-app/line-channel-secret`）
- Lambda 実行ロールに `ssm:GetParameter` 権限を付与（Resource ARN 限定、第7章で詳細）
- Lambda 内で `boto3.client("ssm").get_parameter(Name=..., WithDecryption=True)` で取得
- 取得結果は関数のグローバル変数にキャッシュしてコールドスタート以外では再取得しない

代替案 AWS Secrets Manager との比較:
- Secrets Manager は **シークレットあたり月額 $0.40 + API コール料金** 発生
- SSM Parameter Store の Standard SecureString は **無料**（高度なパラメータを使わない限り）
- 個人ユース・1Bot のスケールでは SSM で十分

注意: chicken-rag のメモリにある「`SecretValue.ssmSecure()` が CFn 側で非対応リソースだとデプロイが落ちる」問題は本プロジェクトでは発生しない。Lambda の `environment` プロパティに渡すのは Parameter **名（平文 string）** であり、`SecretValue` ではないため。

---

## 第3章 handler Lambda 仕様

### 3.1 責務範囲

| 区分 | やる | やらない |
|---|---|---|
| HTTP | LINE webhook の受信・即200返却（5秒以内） | 重い同期処理 |
| 認証 | `X-Line-Signature` 検証（不一致は 403 拒否） | LINE 認可（access_token 検証など） |
| パース | body の JSON パース、`events[]` ループ | LINE 画像コンテンツの取得（content API） |
| テキスト | `登録` で DynamoDB に flag ON、`状態` で flag/コレクション数を返信、その他は無視 | 言葉の解釈（自然言語マッチ） |
| 画像 | DynamoDB から登録モード読出 → SQS に mode 付きでエンキュー → モード OFF に戻す | 画像 DL・S3 アップロード・Rekognition |
| 返信 | テキストコマンドは reply token で即返信、画像受領時は「処理を開始しました」を reply | Push API（processor 側の責務） |

### 3.2 入力イベント（API Gateway → Lambda Proxy 形式）

API Gateway は **Lambda Proxy 統合** で handler を呼ぶ。`event` の主要フィールド:

```json
{
  "httpMethod": "POST",
  "headers": {
    "X-Line-Signature": "Base64(HMAC-SHA256(body, channel_secret))",
    "Content-Type": "application/json"
  },
  "body": "<JSON 文字列>",
  "isBase64Encoded": false
}
```

`event["body"]` は **文字列**（JSON ではなく文字列のまま渡される）。署名検証は **JSON パース前のバイト列** に対して行う必要があるので注意。

`body` をパースした中の LINE webhook ペイロード:

```json
{
  "destination": "U1234...",
  "events": [
    {
      "type": "message",
      "message": {
        "id": "987654321",
        "type": "image",
        "contentProvider": {"type": "line"}
      },
      "replyToken": "abcdef...",
      "source": {"type": "user", "userId": "U1234..."},
      "timestamp": 1234567890
    }
  ]
}
```

LINE webhook 検証用の **空 events 配列**（`events: []`）が来ることがある（LINE Console の Verify ボタン押下時など）。これは何もせず 200 を返す。

### 3.3 出力（Lambda → API Gateway）

| 状況 | statusCode | body |
|---|---|---|
| 正常受領（events 処理済） | 200 | `{"status": "ok"}` |
| events 配列が空（Verify 等） | 200 | `{"status": "ok"}` |
| 署名検証失敗 | 403 | `{"error": "invalid signature"}` |
| body パース失敗 | 400 | `{"error": "invalid json"}` |
| SQS 送信失敗（内部エラー） | 200 | `{"status": "ok"}` ← LINE 側でリトライさせない |

最後の行のポイント: **SQS 送信失敗を 5xx で返すと LINE 側がリトライしてくる**（webhook タイムアウトと同じ扱い）。リトライしても解決しないなら、200 で返してログだけ残し、CloudWatch Alarm で気づく方が運用上安全。

### 3.4 SQS メッセージスキーマ

handler が SQS に投げるメッセージは **2種類** に統一する。`mode` フィールドで分岐。

```json
{
  "mode": "mosaic",
  "userId": "U1234...",
  "messageId": "987654321",
  "timestamp": 1234567890
}
```

```json
{
  "mode": "register",
  "userId": "U1234...",
  "messageId": "987654321",
  "timestamp": 1234567890
}
```

設計上のポイント:

- **`replyToken` は SQS に乗せない**: reply token は受信から1分しか有効でない。processor が SQS から取り出した時点で期限切れの可能性があるため、Push API のみ使う前提にする
- **`messageId`**: LINE の messageId。processor がこれを使って画像をダウンロード（content API）
- **`userId`**: Push API の宛先
- **`timestamp`**: ログ・運用デバッグ用（DLQ 行きになった場合の追跡用）
- **`mode`**: handler が DynamoDB 参照して決める。processor は信じて従う

SQS Standard のメッセージ上限サイズは 256KB だが、上記は数百バイトのメタデータのみなので余裕。

### 3.5 DynamoDB の読み書きパターン

handler が DynamoDB に対して行う操作は3パターン。

| トリガー | 操作 | 内容 |
|---|---|---|
| テキスト `登録` 受信時 | put_item | `{userId, registrationMode: True, ttl: 今+24h}` を upsert |
| 画像受信時（mode 判定） | get_item → put_item | mode 確認後、登録モードを OFF に戻す（連続登録を防ぐ） |
| テキスト `状態` 受信時 | get_item | 登録モードフラグだけ取得（モード表示用） |

#### TTL 計算

```python
import time
TTL_SECONDS_FROM_NOW = 24 * 60 * 60  # 24時間
ttl_value = int(time.time()) + TTL_SECONDS_FROM_NOW
```

DynamoDB TTL は「指定エポック秒を過ぎた項目を最大48時間以内に自動削除」する仕組み。完全な精度ではないが、登録モードのリセット用途なら十分。

#### 画像受信時の get/put のレース

handler が **同一ユーザーの画像を並列に受信**すると、両方が「登録モード ON」を読み取って両方が登録ジョブとして SQS に投げてしまう可能性がある。これを厳密に防ぐには `ConditionExpression` でアトミック更新する必要がある。

ただし本プロジェクトでは:
- 個人ユース（同時投稿の可能性が低い）
- 登録ジョブが2回 SQS に流れても、Rekognition `IndexFaces` は同じ顔を二重登録しない（FaceMatchThreshold で重複検出）

ため、**初版では単純な get_item → put_item で実装し、ConditionExpression は導入しない**。第4章で processor 側の冪等性を担保する。

### 3.6 擬似コード（handler/app.py）

```python
"""LINE webhook 受信 Lambda（軽量・即200返却）"""
import json
import os
import time
import logging
import boto3
from typing import Any

from shared.line_signature import verify_signature
from shared.line_api import LineApiClient

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
REGISTRATION_TABLE_NAME = os.environ["REGISTRATION_TABLE_NAME"]
REKOGNITION_COLLECTION_ID = os.environ["REKOGNITION_COLLECTION_ID"]
LINE_CHANNEL_SECRET_PARAM = os.environ["LINE_CHANNEL_SECRET_PARAM"]
LINE_CHANNEL_ACCESS_TOKEN_PARAM = os.environ["LINE_CHANNEL_ACCESS_TOKEN_PARAM"]

TTL_SECONDS = 24 * 60 * 60

# モジュールレベルでクライアント初期化（コールドスタート時のみ走る）
sqs = boto3.client("sqs")
ddb = boto3.resource("dynamodb")
ssm = boto3.client("ssm")
rekognition = boto3.client("rekognition")
table = ddb.Table(REGISTRATION_TABLE_NAME)

# シークレットはコールドスタート時に取得してキャッシュ
_line_secret_cache: dict[str, str] = {}


def _get_secret(param_name: str) -> str:
    if param_name not in _line_secret_cache:
        resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
        _line_secret_cache[param_name] = resp["Parameter"]["Value"]
    return _line_secret_cache[param_name]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    body_str = event.get("body") or ""
    signature = event.get("headers", {}).get("X-Line-Signature", "")

    # 署名検証
    channel_secret = _get_secret(LINE_CHANNEL_SECRET_PARAM)
    if not verify_signature(body_str, signature, channel_secret):
        LOGGER.warning("invalid signature")
        return _response(403, {"error": "invalid signature"})

    # JSON パース
    try:
        webhook = json.loads(body_str)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid json"})

    line_api = LineApiClient(_get_secret(LINE_CHANNEL_ACCESS_TOKEN_PARAM))

    # events ループ
    for ev in webhook.get("events", []):
        try:
            _handle_event(ev, line_api)
        except Exception as e:
            # 個別イベント失敗で全体を落とさない
            LOGGER.exception("event handling failed: %s", e)

    return _response(200, {"status": "ok"})


def _handle_event(ev: dict[str, Any], line_api: LineApiClient) -> None:
    if ev.get("type") != "message":
        return  # follow/unfollow/postback 等は無視

    message = ev.get("message", {})
    user_id = ev.get("source", {}).get("userId")
    reply_token = ev.get("replyToken", "")
    if not user_id:
        return  # group/room 想定外

    if message.get("type") == "text":
        _handle_text(user_id, message["text"], reply_token, line_api)
    elif message.get("type") == "image":
        _handle_image(user_id, message["id"], reply_token, ev["timestamp"], line_api)


def _handle_text(
    user_id: str, text: str, reply_token: str, line_api: LineApiClient
) -> None:
    text = text.strip()
    if text == "登録":
        table.put_item(Item={
            "userId": user_id,
            "registrationMode": True,
            "ttl": int(time.time()) + TTL_SECONDS,
        })
        line_api.reply(
            reply_token,
            "顔登録モードを開始しました。\n次に1人だけ写った画像を1枚送ってください。",
        )
    elif text == "状態":
        item = table.get_item(Key={"userId": user_id}).get("Item")
        in_mode = bool(item and item.get("registrationMode"))
        face_count = _count_registered_faces()
        line_api.reply(
            reply_token,
            f"登録モード: {'ON' if in_mode else 'OFF'}\n登録済み顔: {face_count}個",
        )
    # それ以外は無視


def _handle_image(
    user_id: str,
    message_id: str,
    reply_token: str,
    timestamp: int,
    line_api: LineApiClient,
) -> None:
    # 登録モード確認
    item = table.get_item(Key={"userId": user_id}).get("Item")
    in_mode = bool(item and item.get("registrationMode"))
    mode = "register" if in_mode else "mosaic"

    # SQS に投入
    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps({
            "mode": mode,
            "userId": user_id,
            "messageId": message_id,
            "timestamp": timestamp,
        }),
    )

    # 登録モードを OFF に戻す（連続登録を防ぐ）
    if in_mode:
        table.put_item(Item={
            "userId": user_id,
            "registrationMode": False,
            "ttl": int(time.time()) + TTL_SECONDS,
        })

    # ユーザーへ即座に状況返信
    msg = "顔を登録しています…" if in_mode else "モザイク処理中です…"
    line_api.reply(reply_token, msg)


def _count_registered_faces() -> int:
    try:
        resp = rekognition.list_faces(CollectionId=REKOGNITION_COLLECTION_ID)
        return len(resp.get("Faces", []))
    except Exception:
        return -1  # 取得失敗時は不明として返す


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "body": json.dumps(body)}
```

### 3.7 エラー処理の方針

| 種類 | 影響範囲 | 方針 |
|---|---|---|
| 署名検証失敗 | 1リクエスト | 403 即返却、ログ警告 |
| JSON パース失敗 | 1リクエスト | 400 即返却 |
| events 配列の特定 event だけ失敗 | 1イベント | try/except で握りつぶし、ループは継続。ログに full スタックトレース |
| SQS 送信失敗 | 1イベント | 上記と同じく except で握る。**5xx を返さない**（LINE がリトライしてくる） |
| DynamoDB アクセス失敗 | 1イベント | 同上 |
| LINE reply API 失敗 | 1イベント | 同上。reply は失敗しても致命的ではない（Push API ベース運用なので） |
| シークレット取得失敗 | 全リクエスト | コールドスタート時に例外 → Lambda 起動失敗。CloudWatch Alarm で検知 |

LINE 側にリトライさせない方針（200 主体）のため、**CloudWatch のエラーログを定期的に見る or SNS 通知を仕込む** 運用が前提。第8章のテスト戦略で handler のエラーアラームも合わせて検討する。

---

## 第4章 processor Lambda 仕様

### 4.1 責務範囲

| 区分 | やる | やらない |
|---|---|---|
| 受信 | SQS から1メッセージずつ処理（batchSize=1） | API Gateway からの直接呼び出し |
| 分岐 | `mode` フィールドで `mosaic` / `register` を分岐 | mode の決定（handler の責務） |
| 共通 | LINE content API で画像 DL、S3 保存 | DynamoDB 操作 |
| mosaic | 顔検出 → 個別照合 → モザイク適用 → presigned URL で Push | reply token 利用（期限切れ） |
| register | 顔検出 → 1件チェック → IndexFaces 登録 → 結果 Push | DynamoDB の registrationMode 更新（handler 側で完結済み） |
| 通知 | LINE Push API（テキスト・画像） | reply API |

### 4.2 入力（SQS Event スキーマ）

Lambda の `event` には複数 `Records` が入りうるが、`batchSize=1` のため 1要素のみ。

```json
{
  "Records": [
    {
      "messageId": "<SQS message ID>",
      "body": "{\"mode\":\"mosaic\",\"userId\":\"U...\",\"messageId\":\"987654321\",\"timestamp\":1234567890}",
      "attributes": {
        "ApproximateReceiveCount": "1"
      }
    }
  ]
}
```

注意点:
- **`record["messageId"]`** は SQS のメッセージ ID（UUID）。**`json.loads(record["body"])["messageId"]`** は LINE のメッセージ ID。混同しないよう変数名を分ける（擬似コードでは `sqs_msg_id` と `line_message_id`）
- **`attributes["ApproximateReceiveCount"]`**: 何回目の試行かを示す。エラー処理でリトライ判定に使う

### 4.3 mosaic モードの処理フロー

```
[SQS] mode=mosaic, userId, messageId
  ↓
1. LINE content API で画像 DL（messageId ベース）
2. S3 アップロード input/{messageId}.jpg
3. Rekognition detect_faces → 顔リスト
   - 0件: Push「顔が検出されませんでした」、終了
4. MOSAIC_MODE=exclude なら個別照合（face_matcher.filter_known_faces_with_limit）
   - 顔数 > 20: 全員モザイク
   - 顔数 ≤ 20: 各顔をクロップ→S3→search_faces_by_image→類似度50%以上を除外
5. PIL でモザイク適用
6. S3 アップロード output/{messageId}.jpg
7. presigned URL（1時間有効）を Push API で送信
```

### 4.4 register モードの処理フロー

```
[SQS] mode=register, userId, messageId
  ↓
1. LINE content API で画像 DL
2. S3 アップロード registration/{userId}/{messageId}.jpg
3. Rekognition detect_faces
   - 0件: Push「顔が検出されませんでした」、終了
   - 2件以上: Push「1人だけが写った画像を送信してください」、終了
   - 1件: 続行
4. Rekognition index_faces (ExternalImageId=line_message_id) で登録 → face_id 取得
5. Push「顔登録が完了しました。登録ID: {face_id[:8]}...」
```

### 4.5 冪等性の確保

SQS Standard は **at-least-once delivery** で、同じメッセージが複数回 processor に届くことがある（visibility timeout 内に処理完了しなかった、ネットワーク再送など）。冪等性を担保しないと、同じ画像が2枚ユーザーに届くなどの事故が起きる。

#### 戦略: S3 キーを LINE messageId ベースにする

| キー | 既存（uuid ベース） | 新（messageId ベース） |
|---|---|---|
| 入力画像 | `input/{uuid}.jpg` | `input/{messageId}.jpg` |
| 出力画像 | `output/{uuid}.jpg` | `output/{messageId}.jpg` |
| 顔クロップ（個別照合用） | `faces/{uuid}/face_{i}_{uuid}.jpg` | `faces/{messageId}/face_{i}.jpg` |
| 登録用画像 | `registration/{user_id}_{uuid}.jpg` | `registration/{userId}/{messageId}.jpg` |

S3 の `put_object` は冪等（同じキーへの上書きは結果が同じ）なので、これで重複処理しても S3 の状態は同じになる。

#### Rekognition IndexFaces の冪等性

`index_faces` は同じ顔画像を再度登録しても **新しい face_id で重複登録** されてしまう（FaceMatchThreshold は detect_faces 側の話）。本プロジェクトでは:

- **ExternalImageId に LINE messageId を設定**: `index_faces(..., ExternalImageId=line_message_id)` のように渡す
- 同じ messageId からの再登録なら ExternalImageId で判別でき、運用面で重複検知できる
- 重複登録自体を厳格に防ぐには、IndexFaces 前に search_faces_by_image で重複チェックを入れる手もあるが、初版では割愛

#### Push API の重複送信

Push API には冪等トークンがない。processor が完全に同じ処理を2回完走した場合、ユーザーに同じ画像が2回届く可能性が残る。これは SQS の `visibility_timeout (1080秒)` を関数 `timeout (180秒)` の6倍に設定することで実質的に防ぐ（180秒の処理が完了していないのに同じメッセージが再配送される確率は極めて低い）。

### 4.6 既存コードの移植マッピング

`lambda-function/` の既存コードを `processor/` にどう移すか。**完全移植 / 一部修正 / 削除** の3カテゴリ。

| 既存ファイル | 行動 | 理由・修正内容 |
|---|---|---|
| `lambda_function.py` | **削除** | エントリポイントは新 `processor/app.py` に書き直し（SQS 駆動になるため） |
| `image_handler.py` | **削除（責務再分割）** | LINE webhook 解釈は handler に移管。画像 DL/モザイク処理ロジックは新 `app.py` 内で再構築 |
| `text_handler.py` | **削除** | テキスト処理は handler 側に完全移管 |
| `registration_state.py` | **削除** | DynamoDB に置き換わる（handler 側の責務） |
| `mosaic_processor.py` | **完全移植** | `detect_faces` / `apply_mosaic` のロジックはそのまま使える |
| `face_matcher.py` | **一部修正** | `from image_handler import upload_to_s3` の循環参照を解消（`s3_client` を引数で渡す） |
| `face_cropper.py` | **完全移植** | 既存のまま使える |
| `collection_manager.py` | **一部修正** | `add_face_to_collection` に `external_image_id` 引数を追加（冪等性確保のため） |
| `config.py` | **削除** | 環境変数の読み出し方が変わる（os.environ 直接、または shared に再構成） |
| `requirements.txt` | **流用** | 内容は同じ（boto3, requests, Pillow） |

`face_matcher.py` の循環参照解消イメージ:

```python
# 旧（循環参照あり）
def filter_faces_individually(...):
    from image_handler import upload_to_s3
    upload_to_s3(face_bytes, face_key, bucket)

# 新（boto3 クライアントを引数化）
def filter_faces_individually(..., s3_client):
    s3_client.put_object(
        Bucket=bucket, Key=face_key, Body=face_bytes,
        ContentType="image/jpeg",
    )
```

### 4.7 擬似コード（processor/app.py）

```python
"""画像処理 Lambda（SQS 駆動）"""
import json
import os
import logging
from io import BytesIO
from typing import Any

import boto3
from PIL import Image

from shared.line_api import LineApiClient

# 既存ロジックの移植先
from mosaic_processor import detect_faces, apply_mosaic
from face_matcher import filter_known_faces_with_limit
from collection_manager import add_face_to_collection

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

S3_BUCKET = os.environ["S3_BUCKET_NAME"]
COLLECTION_ID = os.environ["REKOGNITION_COLLECTION_ID"]
MOSAIC_MODE = os.environ["MOSAIC_MODE"]
LINE_TOKEN_PARAM = os.environ["LINE_CHANNEL_ACCESS_TOKEN_PARAM"]

PRESIGNED_URL_TTL = 3600
FACE_LIMIT = 20
SIMILARITY_THRESHOLD = 50.0

s3 = boto3.client("s3")
ssm = boto3.client("ssm")
_token_cache: dict[str, str] = {}


def _get_token() -> str:
    if "token" not in _token_cache:
        resp = ssm.get_parameter(Name=LINE_TOKEN_PARAM, WithDecryption=True)
        _token_cache["token"] = resp["Parameter"]["Value"]
    return _token_cache["token"]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    line_api = LineApiClient(_get_token())
    failures = []  # 部分失敗用（partial batch response）

    for record in event.get("Records", []):
        sqs_msg_id = record["messageId"]
        receive_count = int(
            record.get("attributes", {}).get("ApproximateReceiveCount", "1")
        )
        msg = json.loads(record["body"])

        try:
            if msg["mode"] == "mosaic":
                _process_mosaic(msg, line_api)
            elif msg["mode"] == "register":
                _process_register(msg, line_api)
            else:
                LOGGER.error("unknown mode: %s", msg.get("mode"))
        except Exception:
            LOGGER.exception(
                "processing failed: line_message_id=%s receive_count=%s",
                msg.get("messageId"), receive_count,
            )
            # 最終試行（DLQ送り直前）のみユーザーに通知
            if receive_count >= 5:
                _safely_notify_failure(line_api, msg.get("userId"))
            failures.append({"itemIdentifier": sqs_msg_id})

    return {"batchItemFailures": failures}


def _process_mosaic(msg: dict, line_api: LineApiClient) -> None:
    user_id = msg["userId"]
    line_message_id = msg["messageId"]

    # 1. LINE から画像取得
    image_data = line_api.download_content(line_message_id)

    # 2. S3 アップロード（messageId ベースで冪等）
    input_key = f"input/{line_message_id}.jpg"
    s3.put_object(
        Bucket=S3_BUCKET, Key=input_key, Body=image_data,
        ContentType="image/jpeg",
    )

    # 3. 顔検出
    faces = detect_faces(S3_BUCKET, input_key)
    if not faces:
        line_api.push_text(user_id, "顔が検出されませんでした。")
        return

    # 4. モザイク対象決定
    if MOSAIC_MODE == "exclude":
        original_image = Image.open(BytesIO(image_data))
        faces_to_mosaic = filter_known_faces_with_limit(
            faces, original_image, S3_BUCKET,
            f"faces/{line_message_id}", COLLECTION_ID,
            face_limit=FACE_LIMIT,
            similarity_threshold=SIMILARITY_THRESHOLD,
            s3_client=s3,  # 循環参照解消のため引数化
        )
    else:
        faces_to_mosaic = faces

    # 5. モザイク適用
    image = Image.open(BytesIO(image_data))
    mosaic_image = apply_mosaic(image, faces_to_mosaic)

    # 6. 出力アップロード
    output_key = f"output/{line_message_id}.jpg"
    output_buffer = BytesIO()
    mosaic_image.save(output_buffer, format="JPEG")
    s3.put_object(
        Bucket=S3_BUCKET, Key=output_key,
        Body=output_buffer.getvalue(), ContentType="image/jpeg",
    )

    # 7. presigned URL → Push API
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": output_key},
        ExpiresIn=PRESIGNED_URL_TTL,
    )
    line_api.push_image(user_id, presigned_url, presigned_url)


def _process_register(msg: dict, line_api: LineApiClient) -> None:
    user_id = msg["userId"]
    line_message_id = msg["messageId"]

    image_data = line_api.download_content(line_message_id)

    image_key = f"registration/{user_id}/{line_message_id}.jpg"
    s3.put_object(
        Bucket=S3_BUCKET, Key=image_key, Body=image_data,
        ContentType="image/jpeg",
    )

    faces = detect_faces(S3_BUCKET, image_key)
    if not faces:
        line_api.push_text(
            user_id,
            "顔が検出されませんでした。別の画像で再度お試しください。",
        )
        return
    if len(faces) > 1:
        line_api.push_text(
            user_id,
            "複数の顔が検出されました。1人だけが写った画像を送信してください。",
        )
        return

    face_id = add_face_to_collection(
        S3_BUCKET, image_key, COLLECTION_ID,
        external_image_id=line_message_id,  # 冪等性確保
    )
    line_api.push_text(
        user_id, f"顔登録が完了しました。\n登録ID: {face_id[:8]}...",
    )


def _safely_notify_failure(
    line_api: LineApiClient, user_id: str | None,
) -> None:
    """DLQ 送り直前のみ呼ばれる。Push 失敗で例外を投げない。"""
    if not user_id:
        return
    try:
        line_api.push_text(
            user_id,
            "画像処理に失敗しました。お手数ですがもう一度送信してください。",
        )
    except Exception:
        LOGGER.exception("failure notification push failed")
```

### 4.8 エラー処理・DLQ 行きの条件

#### 例外発生時の挙動

`raise` した例外は SQS event source mapping によって自動でリトライされる仕組み。試行回数は SQS の `maxReceiveCount=5` に従う。

| ApproximateReceiveCount | 挙動 |
|---|---|
| 1〜4 | Lambda が例外を投げる → visibility_timeout 後に再配送 |
| 5 | Lambda が例外を投げる → DLQ に移送、再配送なし |

#### ユーザー通知のタイミング

「処理失敗」を毎リトライで通知するとユーザーがスパムを受け取る。本仕様では:

- **試行 1〜4 (`receive_count < 5`)**: 通知しない（リトライで成功する可能性あり）
- **試行 5 (`receive_count >= 5`)**: Push API で「処理に失敗しました」を1回だけ通知 → 例外を再発生 → DLQ 送り

これにより、ユーザーには **確定失敗の通知が1回だけ** 届く。

#### Partial Batch Response

`batchSize=1` のため実質意味がないが、将来 batchSize を増やした際に1件失敗で全件リトライにならないよう、`batchItemFailures` を返すパターンで実装する（CDK 側で `report_batch_item_failures=True` を `SqsEventSource` に設定する必要あり、第5章で扱う）。

#### DLQ 監視

DLQ にメッセージが入った場合の検知は CloudWatch Alarm で行う。具体的なメトリクス:
- `AWS/SQS NumberOfMessagesSent` を DLQ の Dimension で監視
- 閾値 1 件以上で通知（SNS → Slack 等）

ただし通知連携の実装は Phase 2 の検証計画外。**Phase 2 の検証時は、テスト後に手動で DLQ コンソールを確認する** ことで代用する（todo.md にも追記済み）。

---

## 第5章 SQS / DLQ 仕様

### 5.1 メインキュー（ProcessorQueue）

| パラメータ | 値 | 根拠 |
|---|---|---|
| `visibility_timeout` | **1080秒（18分）** | processor 関数 timeout 180秒の **6倍**。AWS 公式推奨。リトライ時に同じメッセージが他の Lambda に渡らない時間を確保 |
| `retention_period` | **4日**（SQS デフォルト） | LINE content API の messageId が1週間で失効。4日で十分 |
| `dead_letter_queue` | ProcessorDLQ にリダイレクト | 5回失敗した時の保管庫 |
| `max_receive_count` | **5** | AWS 公式推奨「5以上」。Rekognition の一時的なスロットリングを乗り越える余地 |
| 種別 | **Standard**（FIFO ではない） | 順序保証不要、TPS 無制限、料金安 |
| `delay_seconds` | 0（デフォルト） | 即時処理 |
| `encryption` | **SQS_MANAGED** | AWS マネージド KMS で透過的に暗号化。コスト追加なし |

### 5.2 デッドレターキュー（ProcessorDLQ）

| パラメータ | 値 | 根拠 |
|---|---|---|
| `retention_period` | **14日** | DLQ メッセージは手動調査するもの。最大値で見逃しを防ぐ |
| `visibility_timeout` | 30秒（デフォルト） | DLQ から能動的に消費しない想定 |
| `encryption` | **SQS_MANAGED** | メインキューと揃える |

### 5.3 SqsEventSource（イベントソースマッピング）

processor Lambda と SQS をつなぐコンストラクト。

| パラメータ | 値 | 根拠 |
|---|---|---|
| `batch_size` | **1** | 画像処理は1件ずつ独立。バッチで1件失敗すると他も visibility timeout 待ちになって巻き込み事故になる |
| `report_batch_item_failures` | **True** | `batchItemFailures` を返すパターンで実装するため必須。将来 `batch_size` を増やしても1件単位でリトライ制御できる |
| `enabled` | True（デフォルト） | デプロイ直後から動かす |
| `max_batching_window` | 指定なし（デフォルト 0） | バッチサイズ1なのでウィンドウ意味なし |

### 5.4 並列度制御

processor の同時実行数は **Lambda の `reserved_concurrent_executions` で制限** する方針。

| 設定 | 値 | 役割 |
|---|---|---|
| `reserved_concurrent_executions` (Lambda) | **5** | processor が同時に5並列までしか動かない |
| `max_concurrency` (SqsEventSource) | **指定しない** | Lambda 側で制御、二重指定しない |

並列度を5に絞る根拠:
1. **Rekognition のレート制限**: SearchFacesByImage は 5 TPS。スロットリング回避
2. **LINE Push API 通数制御**: 200通/月の無料枠を急に消費しない
3. **SQS のスケール特性**: SQS は数千 TPS でも捌けるので、processor を無限スケールさせない

`SqsEventSource(max_concurrency=...)` と `reserved_concurrent_executions` を両方指定すると挙動が直感的でないため、**Lambda 側に統一**。

### 5.5 メッセージサイズ

| 種別 | 上限 | 本仕様での実値 |
|---|---|---|
| SQS Standard message size | 256 KB | 数百バイト（mode/userId/messageId/timestamp の JSON） |

画像本体は SQS に乗せず content API で都度 DL するため、サイズ懸念なし。

### 5.6 暗号化

| 項目 | 採否 | 根拠 |
|---|---|---|
| `encryption=sqs.QueueEncryption.SQS_MANAGED` | **採用** | AWS マネージド KMS で透過的に暗号化。追加コストなし、トラフィック制限への影響なし |
| `encryption=sqs.QueueEncryption.KMS` | 不採用 | 顧客管理 CMK が必要なほどの機密ではない |

---

## 第6章 環境変数一覧

### 6.1 全体像

handler / processor の環境変数を整理し、それぞれ「値の来歴」を明示する。

| 変数名 | 関数 | 値の来歴 | 例（実値はコミットしない） |
|---|---|---|---|
| `SQS_QUEUE_URL` | handler | CDK 自動生成（`queue.queue_url`） | `https://sqs.us-east-1.amazonaws.com/.../...` |
| `REGISTRATION_TABLE_NAME` | handler | CDK 自動生成（`table.table_name`） | `MosaicAppV2-RegistrationStateTable-XXX` |
| `REKOGNITION_COLLECTION_ID` | handler, processor | **context 経由**（既存リソース名） | `mosaic-app-collection` |
| `S3_BUCKET_NAME` | processor | **context 経由**（既存リソース名） | `mosaic-app-bucket-xxx` |
| `MOSAIC_MODE` | processor | **context 経由**（または固定 `exclude`） | `exclude` |
| `LINE_CHANNEL_SECRET_PARAM` | handler | **context 経由**（SSM Parameter 名） | `/mosaic-app/line-channel-secret` |
| `LINE_CHANNEL_ACCESS_TOKEN_PARAM` | handler, processor | **context 経由**（SSM Parameter 名） | `/mosaic-app/line-channel-access-token` |

ポイント:
- **CDK 自動生成** は CDK が `queue.queue_url` などで参照を解決し、デプロイ時に Lambda 環境変数として注入される
- **context 経由** は `cdk deploy -c name=value` で渡す。デプロイヘルパースクリプトで `~/.secrets/mosaic-app.env` を読み込んで一括指定する
- **シークレット実値** は環境変数に置かない。SSM Parameter Store の **名前** だけ渡し、Lambda 起動時に `ssm.get_parameter(WithDecryption=True)` で取得する

### 6.2 `~/.secrets/mosaic-app.env` の構造

実値の保管場所はリポジトリ外（メモリ規約）。次の構成。

```bash
# ~/.secrets/mosaic-app.env
# AWS 既存リソース識別情報
S3_BUCKET_NAME=mosaic-app-bucket-xxxxxxxx
REKOGNITION_COLLECTION_ID=mosaic-app-collection

# LINE Bot の機密
LINE_CHANNEL_ACCESS_TOKEN=...（長い文字列）
LINE_CHANNEL_SECRET=...（32文字程度）

# SSM Parameter 名（実値ではなく名前。固定値だが env にまとめておくと参照しやすい）
LINE_CHANNEL_ACCESS_TOKEN_PARAM=/mosaic-app/line-channel-access-token
LINE_CHANNEL_SECRET_PARAM=/mosaic-app/line-channel-secret
```

### 6.3 SSM Parameter Store に置く値

| Parameter 名 | 型 | 値 |
|---|---|---|
| `/mosaic-app/line-channel-secret` | SecureString | `~/.secrets/mosaic-app.env` の `LINE_CHANNEL_SECRET` |
| `/mosaic-app/line-channel-access-token` | SecureString | 同 `LINE_CHANNEL_ACCESS_TOKEN` |

これらは **CDK の管理外**（手動で `aws ssm put-parameter` するか、setup スクリプトで投入）。

理由: CDK で SSM Parameter リソースを作ると、CFn 上にシークレット平文が残る。手動 / 別スクリプトで投入することで、シークレット値が CDK の管轄から完全に分離される。

### 6.4 デプロイヘルパースクリプトの設計

既存メモリ「trip-road デプロイは専用 sh 経由」と同様のパターン。`scripts/` ディレクトリに2本用意。

#### `scripts/setup-secrets.sh`（初回 / シークレット更新時）

```bash
#!/usr/bin/env bash
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
```

#### `scripts/deploy.sh`（通常のデプロイ）

```bash
#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.secrets/mosaic-app.env"

cd "$(dirname "$0")/../cdk"

cdk deploy MosaicAppV2 \
  -c s3_bucket_name="$S3_BUCKET_NAME" \
  -c rekognition_collection_id="$REKOGNITION_COLLECTION_ID" \
  -c line_channel_secret_param="$LINE_CHANNEL_SECRET_PARAM" \
  -c line_channel_access_token_param="$LINE_CHANNEL_ACCESS_TOKEN_PARAM" \
  --require-approval never
```

`--require-approval never` は IAM 変更を含む差分でも対話プロンプトを出さない設定。本プロジェクトは個人用で開発者は1人のため、確認プロンプトを毎回挟む価値が薄い。気になるなら `--require-approval broadening`（広範囲な権限変更時のみ確認）が代替案。

### 6.5 `cdk/app.py` 側で context を読む

`cdk/app.py` は context を受け取って `MosaicStack` に渡す。

```python
import aws_cdk as cdk
from stacks.mosaic_stack import MosaicStack

app = cdk.App()

MosaicStack(app, "MosaicAppV2",
    env=cdk.Environment(region="us-east-1"),
    s3_bucket_name=app.node.try_get_context("s3_bucket_name"),
    rekognition_collection_id=app.node.try_get_context("rekognition_collection_id"),
    line_channel_secret_param=app.node.try_get_context("line_channel_secret_param"),
    line_channel_access_token_param=app.node.try_get_context(
        "line_channel_access_token_param"
    ),
)

app.synth()
```

context が未指定（None）の場合は `MosaicStack.__init__` の引数バリデーションで明確にエラーにする（`raise ValueError`）方針。

---

## 第7章 IAM ポリシー最小権限設計

### 7.1 設計方針

**CDK の `grant_*` メソッドが使えるリソースは自動で最小権限を付与し、既存リソース（CDK スタック外）に対してのみ明示的に PolicyStatement を書く** 方針。

- スタック内リソース（SQS, DynamoDB） → `queue.grant_send_messages(fn)` などで自動
- スタック外リソース（既存 S3, Rekognition, 手動 SSM Parameter） → `add_to_role_policy()` で明示的に Statement を追加
- 信頼ポリシー（`lambda.amazonaws.com`） → `DockerImageFunction` が自動生成

### 7.2 handler Lambda の権限一覧

| Action | Resource | 付与方法 | 用途 |
|---|---|---|---|
| `sqs:SendMessage` | ProcessorQueue ARN | `queue.grant_send_messages(handler_fn)` | mosaic / register ジョブのエンキュー |
| `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem` 等 | RegistrationStateTable ARN | `table.grant_read_write_data(handler_fn)` | 登録モードの読み書き |
| `ssm:GetParameter` | LINE_CHANNEL_SECRET / ACCESS_TOKEN の SSM Parameter ARN（2本） | 明示的 PolicyStatement | 署名検証鍵 / Push API トークン取得 |
| `rekognition:ListFaces` | Rekognition コレクション ARN | 明示的 PolicyStatement | `状態` コマンドで登録顔数表示 |
| `logs:CreateLogStream`, `logs:PutLogEvents` | CloudWatch Logs（実行ロール標準） | CDK 自動 | ログ出力 |

### 7.3 processor Lambda の権限一覧

| Action | Resource | 付与方法 | 用途 |
|---|---|---|---|
| `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` | ProcessorQueue ARN | `queue.grant_consume_messages(processor_fn)` + EventSource 自動 | キュー消費 |
| `s3:GetObject`, `s3:PutObject` | 既存 S3 バケットの `arn/*` | 明示的 PolicyStatement | 入力/出力画像 + 顔クロップ画像の R/W |
| `rekognition:DetectFaces`, `rekognition:IndexFaces`, `rekognition:SearchFacesByImage` | Rekognition コレクション ARN | 明示的 PolicyStatement | 顔検出・登録・照合 |
| `ssm:GetParameter` | LINE_CHANNEL_ACCESS_TOKEN の SSM Parameter ARN（1本のみ） | 明示的 PolicyStatement | Push API トークン取得 |
| `logs:CreateLogStream`, `logs:PutLogEvents` | CloudWatch Logs | CDK 自動 | ログ出力 |

handler と異なり、**signature 検証は不要なので `LINE_CHANNEL_SECRET_PARAM` への権限は付けない**。最小権限の原則。

### 7.4 既存リソースの ARN 形式

CDK スケルトンで参照するために、各リソースの ARN フォーマットを整理。

| リソース | ARN フォーマット |
|---|---|
| 既存 S3 バケット | `arn:aws:s3:::{S3_BUCKET_NAME}` ／ オブジェクト: `arn:aws:s3:::{S3_BUCKET_NAME}/*` |
| Rekognition コレクション | `arn:aws:rekognition:{region}:{account_id}:collection/{REKOGNITION_COLLECTION_ID}` |
| SSM Parameter | `arn:aws:ssm:{region}:{account_id}:parameter{PARAM_NAME}` ※ `PARAM_NAME` に先頭スラッシュ含む |

**SSM Parameter ARN の罠**: パラメータ名に先頭スラッシュ（例: `/mosaic-app/line-channel-secret`）が含まれる場合、ARN の `parameter` の直後にそのまま付ける（`parameter/mosaic-app/line-channel-secret`）。`parameter//mosaic-app/...` のように二重スラッシュにしない。

`account_id` と `region` は CDK のスタック内では `Stack.of(self).account` / `Stack.of(self).region` で取得できる。

### 7.5 CDK 実装イメージ

第2章のスケルトンに以下を **追加** する形。

```python
from aws_cdk import aws_iam as iam

# --- handler の追加権限 ---
account_id = Stack.of(self).account
region = Stack.of(self).region

handler_fn.add_to_role_policy(
    iam.PolicyStatement(
        actions=["ssm:GetParameter"],
        resources=[
            f"arn:aws:ssm:{region}:{account_id}:parameter{line_channel_secret_param}",
            f"arn:aws:ssm:{region}:{account_id}:parameter{line_channel_access_token_param}",
        ],
    )
)
handler_fn.add_to_role_policy(
    iam.PolicyStatement(
        actions=["rekognition:ListFaces"],
        resources=[
            f"arn:aws:rekognition:{region}:{account_id}:collection/{rekognition_collection_id}",
        ],
    )
)

# --- processor の追加権限 ---
processor_fn.add_to_role_policy(
    iam.PolicyStatement(
        actions=["s3:GetObject", "s3:PutObject"],
        resources=[f"arn:aws:s3:::{s3_bucket_name}/*"],
    )
)
processor_fn.add_to_role_policy(
    iam.PolicyStatement(
        actions=[
            "rekognition:DetectFaces",
            "rekognition:IndexFaces",
            "rekognition:SearchFacesByImage",
        ],
        resources=[
            f"arn:aws:rekognition:{region}:{account_id}:collection/{rekognition_collection_id}",
        ],
    )
)
processor_fn.add_to_role_policy(
    iam.PolicyStatement(
        actions=["ssm:GetParameter"],
        resources=[
            f"arn:aws:ssm:{region}:{account_id}:parameter{line_channel_access_token_param}",
        ],
    )
)
```

### 7.6 設計上の注意点

1. **S3 バケットの ListBucket は不要**: 本処理は固定キー（`input/{messageId}.jpg` 等）への直接 R/W のみ。プレフィックス一覧の必要がない
2. **Rekognition のコレクション CreateCollection / DeleteCollection は付けない**: 既存コレクションのみ操作
3. **SSM Parameter Store の `kms:Decrypt` は不要**: SSM SecureString が AWS マネージド `aws/ssm` キーで暗号化されている場合、`ssm:GetParameter` 権限だけで自動的に復号される（顧客管理 CMK を使う場合のみ kms:Decrypt が必要）
4. **handler は S3 / Rekognition の Detect/Index/Search を持たない**: webhook 受信のみが責務、画像処理は processor の責務

---

## 第8章 テスト戦略

### 8.1 テストの全体像

| レイヤー | ツール | カバレッジ目標 | 優先度 |
|---|---|---|---|
| handler 単体 | pytest + moto + unittest.mock | 高（80%以上） | 高 |
| processor 単体 | pytest + moto + unittest.mock | 高（80%以上） | 高 |
| shared 単体 | pytest + unittest.mock | 高（90%以上） | 高 |
| CDK スナップショット | pytest + `aws_cdk.assertions.Template` | 主要リソースの存在確認 | 中 |
| 統合テスト | 手動（実 LINE Bot） | plan.md の検証計画 | 必須（手動） |

選定理由:
- **pytest**: 既存プロジェクトで採用済み、移行コストゼロ
- **moto**: AWS サービスをローカルでモック化する定番ライブラリ。boto3 操作を実際の AWS を呼ばずテスト可能
- **CDK スナップショットテスト**: `cdk synth` の出力から CFn テンプレートを取得し、期待リソースが含まれるかをアサート。回帰防止になる

### 8.2 handler の単体テスト

#### 構造

```
tests/handler/
├── __init__.py
├── conftest.py           # 共通フィクスチャ（moto セットアップ）
├── test_signature.py     # 署名検証パターン
├── test_text_command.py  # 登録 / 状態 / その他
└── test_image.py         # mosaic / register モード分岐
```

#### 主要テストケース

| テスト名 | 観点 |
|---|---|
| `test_invalid_signature_returns_403` | X-Line-Signature 不一致で 403 |
| `test_missing_signature_returns_403` | ヘッダ欠落で 403 |
| `test_empty_events_returns_200` | events 配列が空でも 200 |
| `test_text_register_sets_dynamodb_flag` | 「登録」で DynamoDB に flag 書込 |
| `test_text_status_returns_face_count` | 「状態」で reply に登録顔数を含む |
| `test_text_unknown_does_nothing` | 未知のテキストは無視（DynamoDB / SQS 触らない） |
| `test_image_default_enqueues_mosaic_job` | 通常画像 → SQS に mode=mosaic で送信 |
| `test_image_in_register_mode_enqueues_register_job` | 登録モード中の画像 → mode=register、モード OFF |
| `test_sqs_send_failure_returns_200` | SQS 送信失敗でも 200（LINE にリトライさせない） |

#### moto によるセットアップ例

```python
# tests/handler/conftest.py
import os
import pytest
from moto import mock_aws
import boto3


@pytest.fixture
def aws_mocks():
    with mock_aws():
        ddb = boto3.client("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="test-registration-table",
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue = sqs.create_queue(QueueName="test-queue")
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(
            Name="/mosaic-app/line-channel-secret",
            Value="test-secret", Type="SecureString",
        )
        ssm.put_parameter(
            Name="/mosaic-app/line-channel-access-token",
            Value="test-token", Type="SecureString",
        )
        os.environ.update({
            "SQS_QUEUE_URL": queue["QueueUrl"],
            "REGISTRATION_TABLE_NAME": "test-registration-table",
            "REKOGNITION_COLLECTION_ID": "test-collection",
            "LINE_CHANNEL_SECRET_PARAM": "/mosaic-app/line-channel-secret",
            "LINE_CHANNEL_ACCESS_TOKEN_PARAM": "/mosaic-app/line-channel-access-token",
        })
        yield
```

LINE API の `requests` 呼び出しは `requests_mock` で抑止する。

### 8.3 processor の単体テスト

#### 構造

```
tests/processor/
├── __init__.py
├── conftest.py
├── test_mosaic_flow.py
├── test_register_flow.py
├── test_idempotency.py
└── test_partial_batch_response.py
```

#### 主要テストケース

| テスト名 | 観点 |
|---|---|
| `test_mosaic_normal_path` | 画像 DL → 顔検出 → モザイク → S3 保存 → push_image 呼び出し |
| `test_mosaic_no_faces_pushes_text` | 顔0件で push_text「顔が検出されませんでした」 |
| `test_mosaic_with_known_face_excluded` | 登録済み顔を除外、未知の顔だけにモザイク |
| `test_register_normal_path` | 1顔 → IndexFaces 呼び出し → push_text |
| `test_register_no_faces_pushes_text` | 顔0件で push_text |
| `test_register_multiple_faces_pushes_text` | 2顔以上で push_text |
| `test_idempotent_s3_keys_with_same_message_id` | 同 messageId で2回処理 → S3 キー重複なし |
| `test_failure_at_receive_count_5_notifies_user` | ApproximateReceiveCount=5 で push_text 通知 |
| `test_failure_below_5_does_not_notify_user` | ApproximateReceiveCount=2 では通知しない |
| `test_partial_batch_response_format` | 失敗時に `batchItemFailures` の形式が正しい |

Rekognition は moto のサポート範囲（`detect_faces`, `index_faces`, `search_faces_by_image` など）を活用。サポートされないオペレーションは `unittest.mock.patch` で個別モック。

### 8.4 shared の単体テスト

```
tests/shared/
├── __init__.py
├── test_line_signature.py
└── test_line_api.py
```

| テスト名 | 観点 |
|---|---|
| `test_verify_signature_valid` | 既知のシークレット・本文・期待シグネチャで True |
| `test_verify_signature_tampered_body` | 本文を改ざんすると False |
| `test_verify_signature_wrong_secret` | 違うシークレットで False |
| `test_line_api_reply_calls_correct_endpoint` | reply token 付き POST が `/v2/bot/message/reply` に届く |
| `test_line_api_push_text_format` | Push API の body 構造が公式ドキュメント通り |
| `test_line_api_push_image_format` | 画像 push の `originalContentUrl` / `previewImageUrl` が正しい |
| `test_line_api_download_content_returns_bytes` | 画像 DL で bytes が返る |

`requests` は `requests_mock` でモック。

### 8.5 CDK スナップショットテスト

`aws_cdk.assertions.Template` を使ってスタック構造を検証。

```
cdk/tests/
└── test_mosaic_stack.py
```

| テスト名 | 観点 |
|---|---|
| `test_resource_count` | Lambda 2個、SQS 2個、DynamoDB 1個、API Gateway 関連が想定数あること |
| `test_processor_queue_visibility_timeout` | `VisibilityTimeout: 1080` |
| `test_processor_queue_max_receive_count` | DLQ の `maxReceiveCount: 5` |
| `test_processor_event_source_batch_size_1` | `BatchSize: 1`、`FunctionResponseTypes` に `ReportBatchItemFailures` |
| `test_processor_reserved_concurrency_5` | `ReservedConcurrentExecutions: 5` |
| `test_handler_has_dynamodb_permissions` | RegistrationStateTable への RW 権限が IAM に含まれる |

例:

```python
from aws_cdk import App
from aws_cdk.assertions import Template, Match
from stacks.mosaic_stack import MosaicStack


def test_processor_queue_visibility_timeout():
    app = App()
    stack = MosaicStack(app, "TestStack",
        env={"region": "us-east-1"},
        s3_bucket_name="test-bucket",
        rekognition_collection_id="test-coll",
        line_channel_secret_param="/test/secret",
        line_channel_access_token_param="/test/token",
    )
    template = Template.from_stack(stack)
    template.has_resource_properties(
        "AWS::SQS::Queue",
        Match.object_like({"VisibilityTimeout": 1080}),
    )
```

### 8.6 統合テスト（手動）

CI で自動化はしない。Phase 2-C のデプロイ後に **手動** で実施。`docs/plan.md` の検証計画に沿う。

| 項目 | 手順 | 期待結果 |
|---|---|---|
| 基本動作 | LINE Bot に普通の画像送信 | 数十秒以内に画像返信、Push 経由 |
| 複数登録 | 2人以上登録した状態で集合写真送信 | 全員除外される |
| 20人超 | 21人以上写った写真送信 | 全員モザイク |
| 故意のエラー | LINE Console で webhook URL を 5秒だけ書き換え後戻す等で SQS リトライ発生 | DLQ にメッセージ移送、5回試行後ユーザーに通知 1回 |
| 連続送信 | 10枚連続送信 | 全件返信される、reserved concurrency 5 で順次処理 |
| handler Duration | CloudWatch Logs で確認 | 1秒以下 |
| 登録 | 「登録」→ 1人写真 → push 通知 | 顔登録完了通知 |
| 状態 | 「状態」 | 登録済み顔数が正しい |

### 8.7 既存テスト（`tests/`）の扱い

現状 `tests/` 配下を Phase 2-B 着手時に確認し、以下の方針で振り分ける。

| 既存テスト | 扱い |
|---|---|
| `mosaic_processor` の単体テスト | **流用**（`tests/processor/` に移行） |
| `face_matcher` / `face_cropper` の単体テスト | **流用**（同上） |
| `image_handler` / `text_handler` のテスト | **削除**（責務再分割で対応するファイルが消えるため） |
| `lambda_function` のテスト | **削除** |

---

## Phase 2-A 完了

本仕様書（spec.md 全8章）が Phase 2-A の成果物。次のステップは Phase 2-B 実装。

実装着手前に、新規導入する技術スタック（CDK Python・SQS event source・DynamoDB・Lambda コンテナイメージ）について理解度テストを実施し、合格後に Phase 2-B に進む（CLAUDE.md の理解度テストハーネス規約による）。
