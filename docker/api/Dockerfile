FROM python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY tests /app/tests
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--limit-request-line", "4094", "hermesaki.http:create_app()"]
