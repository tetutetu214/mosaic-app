FROM public.ecr.aws/lambda/python:3.12

# 依存関係をコピー
COPY lambda-function/requirements.txt ${LAMBDA_TASK_ROOT}

# パッケージインストール
RUN pip install -r requirements.txt

# アプリケーションコードをコピー
COPY lambda-function/ ${LAMBDA_TASK_ROOT}

# ハンドラー指定
CMD ["lambda_function.lambda_handler"]