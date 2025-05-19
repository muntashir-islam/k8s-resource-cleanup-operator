FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY k8s_cleanup_operator.py .

# Create directories and set permissions for any user ID
RUN mkdir -p /app/logs /app/tmp && \
    chmod 777 /app/logs /app/tmp && \
    chmod +x /app/k8s_cleanup_operator.py

# Create a minimal user entry for UID 1000 to avoid getpwuid errors
RUN echo "appuser:x:1000:1000:App User:/app:/bin/bash" >> /etc/passwd && \
    echo "appuser:x:1000:" >> /etc/group

# Set environment variables to avoid issues with missing user info
ENV USER=appuser
ENV HOME=/app

# Health check (using kopf's built-in health endpoints)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Run as non-root user
USER 1000:1000

# Run the operator with kopf
CMD ["kopf", "run", "/app/k8s_cleanup_operator.py", "--all-namespaces"]