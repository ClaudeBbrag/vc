# Dockerfile for Seed-VC with GStreamer and CUDA support
# This creates a production-ready container for cloud deployment

FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python
    python3.10 \
    python3-pip \
    python3-dev \
    # GStreamer core and plugins
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-nice \
    gstreamer1.0-rtsp \
    # GStreamer Python bindings
    python3-gi \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gst-plugins-bad-1.0 \
    # Audio libraries
    libsndfile1 \
    libsoundfile1 \
    # Networking
    curl \
    wget \
    netcat \
    # Build tools
    git \
    pkg-config \
    gcc \
    g++ \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt requirements-gstreamer.txt ./

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir -r requirements-gstreamer.txt

# Copy application code
COPY . .

# Create directories for models and data
RUN mkdir -p /app/models /app/data /app/output

# Set up model cache directory
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV TORCH_HOME=/app/models

# Expose ports
# 8080: REST API / Health check
# 5004: RTP input (UDP)
# 5005: RTP output (UDP)
# 8088: Janus WebRTC signaling (if running in same container)
EXPOSE 8080 5004/udp 5005/udp 8088

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import torch; print('CUDA:', torch.cuda.is_available())" || exit 1

# Default command - can be overridden in docker-compose
CMD ["python3", "-u", "server.py"]
