FROM python:3.14-slim AS base

# Install uv (pinned version for reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY icc_eval_server/ icc_eval_server/

# Copy the database file (must be built before docker build)
COPY output/icc-eval.duckdb output/icc-eval.duckdb

# Run as non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "icc_eval_server.server", "--host", "0.0.0.0", "--port", "8000"]
