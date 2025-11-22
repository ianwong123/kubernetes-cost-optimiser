FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY forecasting/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY forecasting/main.py . 

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
 CMD curl -f http://localhost:8002/metrics || exit 1

CMD ["python", "main.py"]