# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Basic OS deps (ca-certificates for HTTPS; tini for clean signals)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only dependency metadata first (better layer caching)
COPY pyproject.toml ./
# If you have a lock file, copy it too (optional):
# COPY requirements.txt ./
# COPY uv.lock ./

# Install package deps (editable install later after copying src)
RUN python -m pip install --no-cache-dir -U pip

# Copy source
COPY src ./src
COPY README.md ./README.md

# Install your project (assumes pyproject defines console_scripts entry for `video-source`)
RUN pip install --no-cache-dir -e .

# Create runtime dirs (optional; volumes also handle this)
RUN mkdir -p /app/cache /app/logs /app/data/results

# Use tini to handle Ctrl+C / signals cleanly
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["video-source", "--help"]
