FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
COPY portfolio-core/ ./portfolio-core/
COPY researcher/ ./researcher/

RUN uv sync --package researcher

RUN mkdir -p /app/memory

CMD ["uv", "run", "--package", "researcher", "python", "-m", "researcher"]
