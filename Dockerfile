# Multi-stage or consolidated lightweight runtime for Adaptive Coding Agent Harness
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies, Git, Node.js, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode CLI globally
RUN npm install -g opencode-ai 2>/dev/null || npm install -g opencode 2>/dev/null || true

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md .env.example ./
COPY src/ ./src/
COPY configs/ ./configs/
COPY benchmark/ ./benchmark/
COPY scripts/ ./scripts/

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip wheel \
    && pip install --no-cache-dir -e . \
    && pip install --no-cache-dir pytest

# Create directory for runs and workspaces
RUN mkdir -p /app/workspace /app/reports

EXPOSE 8000

ENTRYPOINT ["harness"]
CMD ["--help"]
