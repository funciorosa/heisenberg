FROM python:3.11-slim

WORKDIR /app

# Install system deps for numpy/scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY heisenberg/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY heisenberg/ .

CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}
