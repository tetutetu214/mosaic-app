FROM public.ecr.aws/lambda/python:3.12

# ビルドコンテキストはプロジェクトルート
COPY handler/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY shared/ ${LAMBDA_TASK_ROOT}/shared/
COPY handler/app.py ${LAMBDA_TASK_ROOT}/

CMD ["app.lambda_handler"]
