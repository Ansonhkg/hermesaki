FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS client
WORKDIR /build
COPY package.json package-lock.json ./
COPY packages/client/package.json packages/client/package.json
RUN npm ci --ignore-scripts
COPY packages/client packages/client
RUN npm run build
FROM python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY tests /app/tests
COPY landing /app/landing
COPY --from=client /build/packages/client/dist/index.js /app/landing/client.js
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--limit-request-line", "4094", "hermesaki.http:create_app()"]
