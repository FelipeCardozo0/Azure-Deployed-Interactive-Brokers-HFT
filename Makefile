.PHONY: help fmt lint test docker-build docker-push tf-init tf-plan tf-apply tf-destroy k8s-apply k8s-delete paper-test live-promote clean

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

fmt: ## Format code with ruff
	ruff format .

lint: ## Lint code with ruff
	ruff check . --fix

test: ## Run tests with pytest
	pytest tests/ -v --cov=apps --cov=libs --cov-report=html --cov-report=term-missing

docker-build: ## Build all Docker images
	docker build -t hft-ib-azure/ib-gateway:latest apps/ib_gw/
	docker build -t hft-ib-azure/strategy:latest apps/strategy/
	docker build -t hft-ib-azure/risk-oms:latest apps/risk_oms/
	docker build -t hft-ib-azure/md-collector:latest apps/md_collector/
	docker build -t hft-ib-azure/api:latest apps/api/

docker-push: ## Push images to ACR
	az acr login --name $(ACR_NAME)
	docker tag hft-ib-azure/ib-gateway:latest $(ACR_NAME).azurecr.io/ib-gateway:latest
	docker tag hft-ib-azure/strategy:latest $(ACR_NAME).azurecr.io/strategy:latest
	docker tag hft-ib-azure/risk-oms:latest $(ACR_NAME).azurecr.io/risk-oms:latest
	docker tag hft-ib-azure/md-collector:latest $(ACR_NAME).azurecr.io/md-collector:latest
	docker tag hft-ib-azure/api:latest $(ACR_NAME).azurecr.io/api:latest
	docker push $(ACR_NAME).azurecr.io/ib-gateway:latest
	docker push $(ACR_NAME).azurecr.io/strategy:latest
	docker push $(ACR_NAME).azurecr.io/risk-oms:latest
	docker push $(ACR_NAME).azurecr.io/md-collector:latest
	docker push $(ACR_NAME).azurecr.io/api:latest

tf-init: ## Initialize Terraform
	cd infra/terraform && terraform init

tf-plan: ## Plan Terraform changes
	cd infra/terraform && terraform plan -out=tfplan

tf-apply: ## Apply Terraform changes
	cd infra/terraform && terraform apply tfplan

tf-destroy: ## Destroy Terraform resources
	cd infra/terraform && terraform destroy

k8s-apply: ## Apply Kubernetes manifests
	kubectl apply -f infra/k8s/namespace.yaml
	kubectl apply -f infra/k8s/secrets-store-csi-driver.yaml
	kubectl apply -f infra/k8s/kv-secret-providerclass.yaml
	kubectl apply -f infra/k8s/configmap.yaml
	kubectl apply -f infra/k8s/redis-statefulset.yaml
	kubectl apply -f infra/k8s/timescaledb-statefulset.yaml
	kubectl apply -f infra/k8s/kafka-deployment.yaml
	kubectl apply -f infra/k8s/ib-gateway-deployment.yaml
	kubectl apply -f infra/k8s/md-collector-deployment.yaml
	kubectl apply -f infra/k8s/risk-oms-deployment.yaml
	kubectl apply -f infra/k8s/strategy-deployment.yaml
	kubectl apply -f infra/k8s/services.yaml
	kubectl apply -f infra/k8s/hpa.yaml
	kubectl apply -f infra/k8s/networkpolicies.yaml
	kubectl apply -f infra/k8s/cron-ibgw-restart.yaml

k8s-delete: ## Delete Kubernetes resources
	kubectl delete -f infra/k8s/

paper-test: ## Run paper trading integration test
	python tests/integration/test_paper_end_to_end.py

live-promote: ## Promote to live trading (requires manual confirmation)
	@echo "WARNING: This will enable live trading. Are you sure? (y/N)"
	@read -r confirm && [ "$$confirm" = "y" ]
	kubectl patch configmap trading-config -p '{"data":{"ENVIRONMENT":"live"}}'
	kubectl rollout restart deployment/strategy

clean: ## Clean up build artifacts
	rm -rf htmlcov/ .coverage .pytest_cache/
	docker system prune -f
