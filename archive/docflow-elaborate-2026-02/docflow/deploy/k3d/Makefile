# DocFlow Local Development - K3D Makefile
# Mirror of stage/prod configuration for local testing

CLUSTER_NAME := docflow-local
NAMESPACE := docflow
REGISTRY := registry.localhost:5111

# Helm repos
BITNAMI_REPO := https://charts.bitnami.com/bitnami
PROMETHEUS_REPO := https://prometheus-community.github.io/helm-charts
INGRESS_REPO := https://kubernetes.github.io/ingress-nginx

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Cluster Management
# =============================================================================

.PHONY: create-cluster
create-cluster: ## Create K3D cluster
	@echo "Creating K3D cluster..."
	k3d cluster create --config k3d-config.yaml
	@echo "Adding Helm repos..."
	helm repo add bitnami $(BITNAMI_REPO) || true
	helm repo add prometheus-community $(PROMETHEUS_REPO) || true
	helm repo add ingress-nginx $(INGRESS_REPO) || true
	helm repo update
	@echo "Installing NGINX Ingress Controller..."
	helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
		--namespace ingress-nginx \
		--create-namespace \
		--set controller.service.type=LoadBalancer \
		--wait
	@echo "Waiting for ingress controller..."
	kubectl wait --namespace ingress-nginx \
		--for=condition=ready pod \
		--selector=app.kubernetes.io/component=controller \
		--timeout=120s
	@echo "Creating namespace..."
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@echo ""
	@echo "Cluster ready! Run 'make deploy-all' to deploy DocFlow."

.PHONY: delete-cluster
delete-cluster: ## Delete K3D cluster
	k3d cluster delete $(CLUSTER_NAME)

.PHONY: start-cluster
start-cluster: ## Start stopped cluster
	k3d cluster start $(CLUSTER_NAME)

.PHONY: stop-cluster
stop-cluster: ## Stop cluster (preserves state)
	k3d cluster stop $(CLUSTER_NAME)

.PHONY: status
status: ## Show cluster status
	@echo "=== Cluster Status ==="
	k3d cluster list
	@echo ""
	@echo "=== Nodes ==="
	kubectl get nodes
	@echo ""
	@echo "=== Pods in $(NAMESPACE) ==="
	kubectl get pods -n $(NAMESPACE)

# =============================================================================
# Build & Push Images
# =============================================================================

.PHONY: build-images
build-images: build-api build-agent ## Build all images

.PHONY: build-api
build-api: ## Build API image
	docker build -t $(REGISTRY)/docflow-api:local -f ../../docker/Dockerfile.api ../..
	docker push $(REGISTRY)/docflow-api:local

.PHONY: build-agent
build-agent: ## Build Agent image
	docker build -t $(REGISTRY)/docflow-agent:local -f ../../docker/Dockerfile.agent ../..
	docker push $(REGISTRY)/docflow-agent:local

# =============================================================================
# Deploy Infrastructure
# =============================================================================

.PHONY: deploy-infra
deploy-infra: deploy-postgres deploy-redis ## Deploy all infrastructure

.PHONY: deploy-postgres
deploy-postgres: ## Deploy PostgreSQL with pgvector
	@echo "Deploying PostgreSQL with pgvector..."
	helm upgrade --install postgresql bitnami/postgresql \
		--namespace $(NAMESPACE) \
		--values values/postgresql-local.yaml \
		--wait --timeout 5m

.PHONY: deploy-redis
deploy-redis: ## Deploy Redis
	@echo "Deploying Redis..."
	helm upgrade --install redis bitnami/redis \
		--namespace $(NAMESPACE) \
		--values values/redis-local.yaml \
		--wait --timeout 5m

.PHONY: deploy-ollama
deploy-ollama: ## Deploy Ollama for local LLM
	@echo "Deploying Ollama..."
	kubectl apply -f manifests/ollama.yaml -n $(NAMESPACE)
	@echo "Waiting for Ollama to be ready..."
	kubectl wait --for=condition=ready pod -l app=ollama -n $(NAMESPACE) --timeout=300s
	@echo "Pulling embedding model..."
	kubectl exec -n $(NAMESPACE) deploy/ollama -- ollama pull nomic-embed-text

# =============================================================================
# Deploy Application
# =============================================================================

.PHONY: deploy-app
deploy-app: build-images ## Build and deploy DocFlow application
	@echo "Deploying DocFlow..."
	helm upgrade --install docflow ../helm/docflow \
		--namespace $(NAMESPACE) \
		--values values/docflow-local.yaml \
		--set api.image.repository=$(REGISTRY)/docflow-api \
		--set api.image.tag=local \
		--set agent.image.repository=$(REGISTRY)/docflow-agent \
		--set agent.image.tag=local \
		--wait --timeout 5m

.PHONY: deploy-monitoring
deploy-monitoring: ## Deploy monitoring stack (Prometheus, Grafana)
	@echo "Deploying monitoring stack..."
	helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
		--namespace monitoring \
		--create-namespace \
		--values values/monitoring-local.yaml \
		--wait --timeout 10m

# =============================================================================
# Full Stack
# =============================================================================

.PHONY: deploy-all
deploy-all: deploy-infra deploy-ollama deploy-app ## Deploy entire stack
	@echo ""
	@echo "=========================================="
	@echo "  DocFlow Local Development Stack Ready"
	@echo "=========================================="
	@echo ""
	@echo "Access points:"
	@echo "  DocFlow API:    http://localhost:8080"
	@echo "  DocFlow Agent:  ws://localhost:8765"
	@echo "  PostgreSQL:     localhost:5432"
	@echo ""
	@echo "Credentials:"
	@echo "  PostgreSQL:     docflow / localdev"
	@echo ""
	@echo "Commands:"
	@echo "  make logs-api     - View API logs"
	@echo "  make logs-agent   - View Agent logs"
	@echo "  make shell-api    - Shell into API pod"
	@echo "  make test-local   - Run integration tests"
	@echo ""

.PHONY: deploy-all-with-monitoring
deploy-all-with-monitoring: deploy-all deploy-monitoring ## Deploy everything including monitoring
	@echo "  Grafana:        http://localhost:3000 (admin/prom-operator)"

# =============================================================================
# Database Operations
# =============================================================================

.PHONY: db-shell
db-shell: ## Connect to PostgreSQL shell
	kubectl exec -it -n $(NAMESPACE) postgresql-0 -- psql -U docflow -d docflow

.PHONY: db-migrate
db-migrate: ## Run database migrations
	kubectl exec -it -n $(NAMESPACE) deploy/docflow-api -- docflow db migrate

.PHONY: db-seed
db-seed: ## Seed database with sample data
	kubectl exec -it -n $(NAMESPACE) deploy/docflow-api -- docflow db seed

.PHONY: db-reset
db-reset: ## Reset database (WARNING: destroys all data)
	kubectl exec -it -n $(NAMESPACE) deploy/docflow-api -- docflow db reset --yes

# =============================================================================
# Logs & Debugging
# =============================================================================

.PHONY: logs-api
logs-api: ## Tail API logs
	kubectl logs -f -l app.kubernetes.io/name=docflow,app.kubernetes.io/component=api -n $(NAMESPACE)

.PHONY: logs-agent
logs-agent: ## Tail Agent logs
	kubectl logs -f -l app.kubernetes.io/name=docflow,app.kubernetes.io/component=agent -n $(NAMESPACE)

.PHONY: logs-postgres
logs-postgres: ## Tail PostgreSQL logs
	kubectl logs -f -l app.kubernetes.io/name=postgresql -n $(NAMESPACE)

.PHONY: logs-ollama
logs-ollama: ## Tail Ollama logs
	kubectl logs -f -l app=ollama -n $(NAMESPACE)

.PHONY: shell-api
shell-api: ## Shell into API pod
	kubectl exec -it -n $(NAMESPACE) deploy/docflow-api -- /bin/bash

.PHONY: shell-agent
shell-agent: ## Shell into Agent pod
	kubectl exec -it -n $(NAMESPACE) deploy/docflow-agent -- /bin/bash

# =============================================================================
# Port Forwarding
# =============================================================================

.PHONY: port-forward-db
port-forward-db: ## Forward PostgreSQL port
	kubectl port-forward svc/postgresql 5432:5432 -n $(NAMESPACE)

.PHONY: port-forward-api
port-forward-api: ## Forward API port
	kubectl port-forward svc/docflow-api 8080:80 -n $(NAMESPACE)

.PHONY: port-forward-agent
port-forward-agent: ## Forward Agent WebSocket port
	kubectl port-forward svc/docflow-agent 8765:8765 -n $(NAMESPACE)

.PHONY: port-forward-grafana
port-forward-grafana: ## Forward Grafana port
	kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring

# =============================================================================
# Testing
# =============================================================================

.PHONY: test-local
test-local: ## Run integration tests against local cluster
	@echo "Running integration tests..."
	cd ../.. && DATABASE_URL=postgresql://docflow:localdev@localhost:5432/docflow \
		pytest tests/integration/ -v

.PHONY: test-smoke
test-smoke: ## Run smoke tests
	@echo "Running smoke tests..."
	curl -f http://localhost:8080/health || (echo "API health check failed" && exit 1)
	curl -f http://localhost:8080/ready || (echo "API readiness check failed" && exit 1)
	@echo "Smoke tests passed!"

# =============================================================================
# Cleanup
# =============================================================================

.PHONY: clean-app
clean-app: ## Remove DocFlow application
	helm uninstall docflow -n $(NAMESPACE) || true

.PHONY: clean-infra
clean-infra: ## Remove infrastructure (PostgreSQL, Redis)
	helm uninstall postgresql -n $(NAMESPACE) || true
	helm uninstall redis -n $(NAMESPACE) || true
	kubectl delete -f manifests/ollama.yaml -n $(NAMESPACE) || true

.PHONY: clean-monitoring
clean-monitoring: ## Remove monitoring stack
	helm uninstall prometheus -n monitoring || true

.PHONY: clean
clean: clean-app clean-infra clean-monitoring ## Remove everything but keep cluster

.PHONY: nuke
nuke: delete-cluster ## Delete cluster and all data
	rm -rf /tmp/k3d-docflow-storage
	@echo "Cluster and all data deleted."
