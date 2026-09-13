FROM python:3.11-slim

# Install only necessary build dependencies (if any are actually needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory so relative paths inside the code point to /app
WORKDIR /app

# Install the repository-wide, pinned dependency set.
COPY services/ingestion/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire services package (including __init__.py files)
COPY services/ ./services/
COPY data/ /app/data/
# Ensure .env is NOT copied into the image (use .dockerignore)
# Data should be mounted as a volume at runtime, not baked in.

# Set Python to run in unbuffered mode (fixed typo)
ENV PYTHONUNBUFFERED=1

# Run the full ingestion pipeline
CMD ["python", "-m", "services.ingestion.run_ingestion"]