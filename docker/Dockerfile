FROM python:3.12-slim

# Create non-root user for security (Deployment Hygiene)
RUN useradd -m -u 1000 kukanilea

WORKDIR /app

# System dependencies for OCR (Tesseract)
RUN apt-get update && apt-get install -y 
    tesseract-ocr 
    tesseract-ocr-deu 
    tesseract-ocr-eng 
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set permissions
RUN chown -R kukanilea:kukanilea /app

# Switch to non-root user
USER kukanilea

ENV PORT=5051
EXPOSE 5051

CMD ["python", "run.py", "--server", "--host", "0.0.0.0", "--port", "5051"]
