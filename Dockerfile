# ═══════════════════════════════════════════════════════════
# Knowledge Foundry — Backend API Dockerfile
# Multi-stage build: builder → slim runtime
# ═══════════════════════════════════════════════════════════

# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --prefix=/install . packaging

COPY src/ ./src/

# ── Stage 2: Runtime ──
FROM python:3.12-slim AS runtime

LABEL maintainer="Knowledge Foundry Team"
LABEL description="Knowledge Foundry API — Enterprise RAG Platform"

# Security: non-root user
RUN groupadd -r kfuser && useradd -r -g kfuser -d /app -s /sbin/nologin kfuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /build/src ./src

# Install uvicorn for production serving
RUN pip install --no-cache-dir uvicorn[standard] packaging

# Set Python path so src/ is importable
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root
USER kfuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
