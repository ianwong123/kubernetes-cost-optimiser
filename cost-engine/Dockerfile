FROM python:3.11-slim

WORKDIR /app

COPY cost-engine/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY shared-cost-lib/cost_calculator.py .

COPY cost-engine/main.py .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
 CMD curl -f http://localhost:8000/metrics || exit 1

CMD ["python", "main.py"]