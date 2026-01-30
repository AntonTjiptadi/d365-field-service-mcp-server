# ============================================
# Dockerfile for D365 MCP Server
# ============================================
# This Dockerfile creates a containerized version of the MCP server
# for deployment to Azure Container Instances or other container platforms
# ============================================

# Use official Python slim image for smaller size
FROM python:3.11-slim

# Set metadata
LABEL maintainer="antony@voltes.onmicrosoft.com"
LABEL description="MCP Server for Dynamics 365 Field Service Integration"
LABEL version="0.1.0"

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/app \
    # UV installation path
    UV_HOME=/usr/local/bin \
    # Prevent UV from checking for updates during build
    UV_NO_UPDATE_CHECK=1\
    # Add uv to PATH
    PATH="/root/.cargo/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Required for MSAL/cryptography
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    # Useful for debugging
    curl \
    # Clean up to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    echo "=== Checking uv installation ===" && \
    ls -la /root/.cargo/bin/ && \
    /root/.cargo/bin/uv --version || echo "uv command failed"

# Add uv to PATH for subsequent commands and runtime
ENV PATH="/root/.local/bin:${PATH}"

# Debug: verify uv installation
RUN which uv || echo "uv not found in PATH" && ls -la /root/.cargo/bin/ || echo "cargo bin directory not found"

# Copy dependency files first (for better Docker layer caching)
COPY pyproject.toml ./
COPY README.md ./
COPY uv.lock ./

# Create src directory structure
RUN mkdir -p src/mcp_d365fs_server

# Copy source code
COPY src/ ./src/

# Install Python dependencies using uv
# This creates a .venv in the container
RUN uv sync --frozen

# Create directory for environment files
RUN mkdir -p /app/config

# Set Python path to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Expose port (not used for STDIO, but useful for health checks)
EXPOSE 8080

# Add health check script
RUN echo '#!/bin/bash\nexit 0' > /app/healthcheck.sh && chmod +x /app/healthcheck.sh

# Health check (simple for now, can be enhanced)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/app/healthcheck.sh"]

# Default command: Run MCP server
# Note: In production, you'd typically override this with specific commands
EXPOSE 8000

CMD ["uv", "run", "mcp-server"]

# ============================================
# Build Instructions:
# ============================================
# 1. Build the image:
#    docker build -t mcp-d365-server:latest .
#
# 2. Run locally for testing:
#    docker run -it --rm \
#      --env-file .env.trial \
#      mcp-d365-server:latest
#
# 3. Run with custom environment:
#    docker run -it --rm \
#      -e TENANT_ID=your-tenant \
#      -e CLIENT_ID=your-client \
#      -e CLIENT_SECRET=your-secret \
#      -e D365_URL=your-d365-url \
#      -e D365_SCOPE=your-scope \
#      mcp-d365-server:latest
# ============================================

# ============================================
# Production Notes:
# ============================================
# For production deployment:
# 1. Use Azure Key Vault for secrets (not environment variables)
# 2. Add proper logging configuration
# 3. Implement real health check endpoint
# 4. Use non-root user for security
# 5. Scan image for vulnerabilities
# 6. Use specific version tags (not 'latest')
# ============================================
