FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/backend-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY services/__init__.py ./services/__init__.py
COPY services/common/ ./services/common/
COPY services/ingestion/ ./services/ingestion/
COPY services/classifier_service/ ./services/classifier_service/
COPY services/agent_orchestrator/ ./services/agent_orchestrator/
COPY services/backend-api/ ./services/backend_api/
COPY params.yml .

ENV PYTHONUNBUFFERED=1

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "120", "services.backend_api.app:app"]