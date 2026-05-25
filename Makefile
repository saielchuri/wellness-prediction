.PHONY: up down build test train ingest features pipeline push deploy setup run-cloud

PROJECT_ID ?= nytia-dev
REGION ?= northamerica-northeast1
VERSION ?= v1.0.0

# ── Local Development (Docker Compose) ──
up:
	docker compose up -d
	@echo "API:      http://localhost:8000/docs"

up-dev:
	docker compose --profile dev up -d
	@echo "API:      http://localhost:8000/docs"
	@echo "Jupyter:  http://localhost:8888"

down:
	docker compose --profile dev --profile train down

build:
	docker compose build

ingest:
	docker compose run --rm ingestion

features:
	docker compose run --rm features

train:
	docker compose --profile train run --rm model

pipeline: ingest features train
	@echo "Local pipeline complete."

test:
	docker compose run --rm model pytest /app/tests/ -v

logs:
	docker compose logs -f

clean:
	docker compose --profile dev --profile train down -v
	rm -rf data/raw/* data/processed/* models/artifacts/* models/shap_reports/* outputs/*

# ── GCP Deployment (Cloud Run) ──
setup:
	bash scripts/gcp_setup.sh $(PROJECT_ID) $(REGION)

push:
	bash scripts/build_and_push.sh $(PROJECT_ID) $(REGION) $(VERSION)

deploy:
	bash scripts/deploy_cloud_run.sh $(PROJECT_ID) $(REGION) $(VERSION)

run-cloud:
	bash scripts/run_pipeline.sh $(REGION)

# ── Full GCP workflow ──
ship: push deploy
	@echo "Build, push, and deploy complete."
