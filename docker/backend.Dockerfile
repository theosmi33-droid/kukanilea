# Stage 1: Build/Install
FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends 
    build-essential 
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies (like tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends 
    tesseract-ocr 
    tesseract-ocr-deu 
    libpq-dev 
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos "" kukanilea
RUN chown -R kukanilea:kukanilea /app
USER kukanilea

EXPOSE 8000

CMD ["uvicorn", "kukanilea_app:app", "--host", "0.0.0.0", "--port", "8000"]
