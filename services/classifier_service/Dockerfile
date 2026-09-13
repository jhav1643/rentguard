FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/classifier_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/__init__.py ./services/__init__.py
COPY data/ /app/data/
RUN mkdir -p /app/mlflow
COPY services/common/ ./services/common/
COPY services/classifier_service/ ./services/classifier_service/
COPY params.yml .
RUN mkdir -p /mlflow

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "\
    python -m services.classifier_service.training.data_prep && \
    python -m services.classifier_service.training.train && \
    python -m services.classifier_service.training.evaluate \
    "]

