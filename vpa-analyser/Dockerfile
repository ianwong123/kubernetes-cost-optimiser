FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY vpa-analyser/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY shared-cost-lib/cost_calculator.py .

COPY vpa-analyser/main.py .

EXPOSE 8001 

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
 CMD curl -f http://localhost:8001/metrics || exit 1 

CMD ["python", "main.py"]
