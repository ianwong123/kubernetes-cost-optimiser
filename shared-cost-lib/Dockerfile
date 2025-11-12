FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY cost_calculator.py .

RUN if [ -s requirements.txt ] && ! grep -q "^#" requirements.txt; then pip install --no-cache-dir -r requirements.txt; fi

CMD ["python", "-c", "import cost_calculator; print('Shared cost library ready')"]