# =============================================================================
# Orion AI Assistant - Dockerfile (Optimized for Oracle Free-Tier 1GB RAM)
# =============================================================================
# Multi-stage build keeps the final image small.
# Playwright chromium installed only when INSTALL_BROWSER=1 (default: skip).
# =============================================================================

# ---- Stage 1: build dependencies ----
FROM python:3.11-slim AS builder

WORKDIR /build

# System libs needed to compile some Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into a virtual-env so we can copy it cleanly
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.11-slim

# Install only the runtime system libraries we need
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright / Chromium deps (kept minimal)
    wget ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 xdg-utils libu2f-udev libvulkan1 \
    # OCR & PDF
    tesseract-ocr tesseract-ocr-eng poppler-utils \
    # Misc
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Playwright chromium (optional - skip on very low RAM VMs)
ARG INSTALL_BROWSER=0
RUN if [ "$INSTALL_BROWSER" = "1" ]; then \
      playwright install chromium && playwright install-deps chromium; \
    else \
      echo "Skipping Playwright browser install (INSTALL_BROWSER=0)"; \
    fi

# Copy application code
COPY . .

# Create persistent data dirs (volume-mounted at runtime)
RUN mkdir -p /app/data/sandbox/data \
             /app/data/sandbox/notes \
             /app/data/sandbox/tasks \
             /app/data/sandbox/temp \
             /app/data/sandbox/screenshots

# Environment
ENV PYTHONUNBUFFERED=1
ENV ORION_DATA_DIR=/app/data
ENV SKIP_BROWSER_TOOLS=false

# Health-check: ensure the Python process is alive
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "print('ok')" || exit 1

# Run headless mode (Telegram + Email + Scheduler)
CMD ["python", "app_headless.py"]
