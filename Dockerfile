FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install . && pip install "PyYAML>=6.0"

# Run as non-root
USER 65534:65534

EXPOSE 9101

ENTRYPOINT ["langfuse-prometheus-exporter"]
