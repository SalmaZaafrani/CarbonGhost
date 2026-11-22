FROM python:3.12-slim
WORKDIR /app
COPY services/service-ia/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries 10 -r requirements.txt
COPY services/service-ia/ .
COPY shared/ ./shared/
EXPOSE 8004
CMD ["python", "main.py"]
