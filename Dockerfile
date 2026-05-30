FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Create non-root user
RUN adduser --disabled-password --gecos "" --uid 1000 appuser

COPY pyproject.toml uv.lock README.md ./
COPY migrations ./migrations
COPY src ./src

RUN uv sync --frozen --no-dev

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["uv", "run", "--no-dev", "ib-read-model"]
