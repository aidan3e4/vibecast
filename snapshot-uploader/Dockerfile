FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install minimal dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY uploader.py .

# Create snapshots directory (for filesystem backend)
RUN mkdir -p /app/snapshots

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Run as non-root user
RUN useradd -m -u 1000 uploader && \
    chown -R uploader:uploader /app
USER uploader

# Default command
CMD ["python", "-u", "uploader.py"]
