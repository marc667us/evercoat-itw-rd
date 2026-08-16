# EvercoatITWRD APP — API image
# Multi-stage: build wheels once, ship a slim runtime without a compiler.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-only. These do not reach the runtime image, which keeps the
# attack surface and the Trivy report small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
# Dependency layer is cached separately from source, so an edit to a
# handler does not rebuild the scientific stack.
RUN pip wheel --wheel-dir /wheels -e . 2>/dev/null || \
    (pip install --upgrade pip hatchling && pip wheel --wheel-dir /wheels -e .)


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libpq5 only — the client library, not the dev headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root. A container running as root that is subject to FORCE RLS is
# still a container an attacker would rather have than not.
RUN useradd --create-home --uid 10001 evercoat

WORKDIR /app
COPY --from=builder /wheels /wheels
COPY pyproject.toml ./
RUN pip install --no-index --find-links=/wheels -e . && rm -rf /wheels

COPY --chown=evercoat:evercoat . .

USER evercoat
EXPOSE 8000

# Compose owns the healthcheck so the probe definition lives beside the
# service it guards, not split across two files.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
