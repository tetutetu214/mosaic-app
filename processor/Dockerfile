FROM public.ecr.aws/lambda/python:3.12

# ビルドコンテキストはプロジェクトルート
COPY processor/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY shared/ ${LAMBDA_TASK_ROOT}/shared/
COPY processor/ ${LAMBDA_TASK_ROOT}/

CMD ["app.lambda_handler"]
