# YouTube Downloader Dockerfile
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Download FFmpeg static binary
RUN mkdir -p /app/static/ffmpeg && \
    wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -O /tmp/ffmpeg.tar.xz && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    cp /tmp/ffmpeg-*-amd64-static/ffmpeg /app/static/ffmpeg/ && \
    cp /tmp/ffmpeg-*-amd64-static/ffprobe /app/static/ffmpeg/ && \
    chmod +x /app/static/ffmpeg/ffmpeg /app/static/ffmpeg/ffprobe && \
    rm -rf /tmp/ffmpeg* && \
    apt-get remove -y wget xz-utils && \
    apt-get autoremove -y && \
    apt-get clean

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /app/downloads

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/api/health')" || exit 1

# Run the application
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "300", "--keep-alive", "5"]