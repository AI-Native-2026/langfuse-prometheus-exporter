.PHONY: install dev test lint run docker-build docker-run

install:
	pip install .

dev:
	pip install -e ".[yaml,test]"

test:
	pytest

run:
	langfuse-prometheus-exporter

docker-build:
	docker build -t langfuse-prometheus-exporter:local .

docker-run:
	docker run --rm -p 9101:9101 \
		-e LANGFUSE_HOST=$${LANGFUSE_HOST:-http://localhost:3000} \
		-e LANGFUSE_PUBLIC_KEY=$${LANGFUSE_PUBLIC_KEY} \
		-e LANGFUSE_SECRET_KEY=$${LANGFUSE_SECRET_KEY} \
		langfuse-prometheus-exporter:local
