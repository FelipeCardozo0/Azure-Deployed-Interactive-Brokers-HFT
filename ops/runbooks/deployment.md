# Deployment Runbook

## Overview
This runbook provides step-by-step procedures for deploying the HFT trading system to Azure.

## Prerequisites

### Required Tools
- Azure CLI (`az`)
- Terraform (`terraform`)
- kubectl
- Docker
- Helm (optional)

### Required Access
- Azure subscription access
- AKS cluster access
- Container registry access
- Key Vault access

## Deployment Process

### 1. Infrastructure Deployment

#### 1.1 Initialize Terraform
```bash
cd infra/terraform
terraform init
```

#### 1.2 Plan Infrastructure
```bash
# Review the plan
terraform plan -var-file="production.tfvars"
```

#### 1.3 Deploy Infrastructure
```bash
# Deploy infrastructure
terraform apply -var-file="production.tfvars"
```

#### 1.4 Verify Infrastructure
```bash
# Check resource group
az group show --name hft-trading-rg

# Check AKS cluster
az aks show --name hft-aks --resource-group hft-trading-rg

# Check database
az postgres flexible-server show --name hft-postgres --resource-group hft-trading-rg

# Check Redis
az redis show --name hft-redis --resource-group hft-trading-rg
```

### 2. Container Registry Setup

#### 2.1 Login to ACR
```bash
# Get ACR login server
ACR_NAME=$(terraform output -raw acr_name)
az acr login --name $ACR_NAME
```

#### 2.2 Build and Push Images
```bash
# Build and push IB Gateway
docker build -t $ACR_NAME.azurecr.io/ib-gateway:latest apps/ib_gw/
docker push $ACR_NAME.azurecr.io/ib-gateway:latest

# Build and push MD Collector
docker build -t $ACR_NAME.azurecr.io/md-collector:latest apps/md_collector/
docker push $ACR_NAME.azurecr.io/md-collector:latest

# Build and push Strategy
docker build -t $ACR_NAME.azurecr.io/strategy:latest apps/strategy/
docker push $ACR_NAME.azurecr.io/strategy:latest

# Build and push Risk/OMS
docker build -t $ACR_NAME.azurecr.io/risk-oms:latest apps/risk_oms/
docker push $ACR_NAME.azurecr.io/risk-oms:latest

# Build and push API
docker build -t $ACR_NAME.azurecr.io/api:latest apps/api/
docker push $ACR_NAME.azurecr.io/api:latest
```

### 3. Kubernetes Deployment

#### 3.1 Configure kubectl
```bash
# Get AKS credentials
az aks get-credentials --name hft-aks --resource-group hft-trading-rg
```

#### 3.2 Deploy Namespace
```bash
kubectl apply -f infra/k8s/namespace.yaml
```

#### 3.3 Deploy Secrets Store CSI Driver
```bash
kubectl apply -f infra/k8s/secrets-store-csi-driver.yaml
```

#### 3.4 Deploy Secret Provider Class
```bash
# Update values in secret-provider-class.yaml
kubectl apply -f infra/k8s/secret-provider-class.yaml
```

#### 3.5 Deploy IB Gateway
```bash
kubectl apply -f infra/k8s/ib-gateway-deployment.yaml
```

#### 3.6 Deploy Market Data Collector
```bash
kubectl apply -f infra/k8s/md-collector-deployment.yaml
```

#### 3.7 Deploy Strategy
```bash
kubectl apply -f infra/k8s/strategy-deployment.yaml
```

#### 3.8 Deploy Risk/OMS
```bash
kubectl apply -f infra/k8s/risk-oms-deployment.yaml
```

#### 3.9 Deploy API
```bash
kubectl apply -f infra/k8s/api-deployment.yaml
```

### 4. Database Setup

#### 4.1 Connect to Database
```bash
# Get connection string
POSTGRES_CONN=$(terraform output -raw postgres_connection_string)
```

#### 4.2 Run Database Migrations
```bash
# Run Alembic migrations
kubectl exec -n trading deployment/api -- alembic upgrade head
```

#### 4.3 Create TimescaleDB Extensions
```sql
-- Connect to database and run
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

#### 4.4 Create Tables
```sql
-- Create market data tables
CREATE TABLE IF NOT EXISTS ticks (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    bid DECIMAL(10,2),
    ask DECIMAL(10,2),
    last DECIMAL(10,2),
    bid_size INTEGER,
    ask_size INTEGER,
    last_size INTEGER,
    volume BIGINT
);

CREATE TABLE IF NOT EXISTS bars (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    interval VARCHAR(10) NOT NULL
);

-- Create trading tables
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2),
    order_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    correlation_id VARCHAR(50),
    idempotency_key VARCHAR(50) UNIQUE
);

CREATE TABLE IF NOT EXISTS fills (
    id BIGSERIAL PRIMARY KEY,
    fill_id VARCHAR(50) UNIQUE NOT NULL,
    order_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    commission DECIMAL(10,2),
    correlation_id VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    avg_cost DECIMAL(10,2) NOT NULL,
    market_value DECIMAL(10,2) NOT NULL,
    unrealized_pnl DECIMAL(10,2) NOT NULL,
    realized_pnl DECIMAL(10,2) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pnl (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    realized_pnl DECIMAL(10,2) NOT NULL,
    unrealized_pnl DECIMAL(10,2) NOT NULL,
    total_pnl DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    value DECIMAL(15,6) NOT NULL,
    tags JSONB,
    timestamp TIMESTAMPTZ NOT NULL
);

-- Create hypertables
SELECT create_hypertable('ticks', 'timestamp');
SELECT create_hypertable('bars', 'timestamp');
SELECT create_hypertable('orders', 'created_at');
SELECT create_hypertable('fills', 'timestamp');
SELECT create_hypertable('positions', 'updated_at');
SELECT create_hypertable('pnl', 'timestamp');
SELECT create_hypertable('metrics', 'timestamp');

-- Create indexes
CREATE INDEX idx_ticks_symbol_timestamp ON ticks (symbol, timestamp);
CREATE INDEX idx_bars_symbol_timestamp ON bars (symbol, timestamp);
CREATE INDEX idx_orders_symbol_created_at ON orders (symbol, created_at);
CREATE INDEX idx_fills_order_id ON fills (order_id);
CREATE INDEX idx_positions_symbol ON positions (symbol);
CREATE INDEX idx_pnl_symbol_timestamp ON pnl (symbol, timestamp);
CREATE INDEX idx_metrics_name_timestamp ON metrics (name, timestamp);
```

### 5. Monitoring Setup

#### 5.1 Deploy Prometheus
```bash
# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Deploy Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values ops/monitoring/prometheus-values.yaml
```

#### 5.2 Deploy Grafana
```bash
# Deploy Grafana
helm install grafana grafana/grafana \
  --namespace monitoring \
  --values ops/monitoring/grafana-values.yaml
```

#### 5.3 Configure Alerting
```bash
# Deploy alert rules
kubectl apply -f ops/monitoring/alert-rules.yaml
```

### 6. Verification

#### 6.1 Check Pod Status
```bash
kubectl get pods -n trading
kubectl get pods -n monitoring
```

#### 6.2 Check Services
```bash
kubectl get services -n trading
kubectl get services -n monitoring
```

#### 6.3 Check Ingress
```bash
kubectl get ingress -n trading
```

#### 6.4 Test API Endpoints
```bash
# Test health endpoint
curl http://api.trading.example.com/api/v1/health

# Test kill switch
curl -X POST http://api.trading.example.com/api/v1/kill_switch \
     -H "Content-Type: application/json" \
     -d '{"active": false, "reason": "Deployment test"}'

# Test positions
curl http://api.trading.example.com/api/v1/positions

# Test PnL
curl http://api.trading.example.com/api/v1/pnl
```

#### 6.5 Check Logs
```bash
# Check IB Gateway logs
kubectl logs -n trading deployment/ib-gateway --tail=100

# Check MD Collector logs
kubectl logs -n trading deployment/md-collector --tail=100

# Check Strategy logs
kubectl logs -n trading deployment/strategy --tail=100

# Check Risk/OMS logs
kubectl logs -n trading deployment/risk-oms --tail=100

# Check API logs
kubectl logs -n trading deployment/api --tail=100
```

#### 6.6 Check Metrics
```bash
# Check Prometheus metrics
curl http://prometheus.monitoring.svc.cluster.local:9090/api/v1/query?query=up

# Check Grafana
# Access Grafana UI and verify dashboards
```

### 7. Post-Deployment

#### 7.1 Update DNS
```bash
# Update DNS records to point to the ingress
# This depends on your DNS provider
```

#### 7.2 Configure SSL Certificates
```bash
# Deploy SSL certificates
kubectl apply -f infra/k8s/ssl-certificates.yaml
```

#### 7.3 Configure Monitoring and Alerting
```bash
# Deploy monitoring dashboards
kubectl apply -f ops/monitoring/dashboards/

# Deploy alert rules
kubectl apply -f ops/monitoring/alert-rules.yaml
```

#### 7.4 Run Smoke Tests
```bash
# Run integration tests
kubectl exec -n trading deployment/api -- python -m pytest tests/integration/

# Run paper trading tests
kubectl exec -n trading deployment/api -- python -m pytest tests/integration/test_paper_end_to_end.py
```

## Rollback Procedures

### 1. Application Rollback
```bash
# Rollback specific deployment
kubectl rollout undo deployment/strategy -n trading
kubectl rollout undo deployment/risk-oms -n trading
kubectl rollout undo deployment/md-collector -n trading
kubectl rollout undo deployment/api -n trading
```

### 2. Infrastructure Rollback
```bash
# Rollback infrastructure changes
cd infra/terraform
terraform plan -var-file="production.tfvars"
terraform apply -var-file="production.tfvars"
```

### 3. Database Rollback
```bash
# Rollback database migrations
kubectl exec -n trading deployment/api -- alembic downgrade -1
```

## Troubleshooting

### Common Issues

#### 1. Pod Startup Issues
```bash
# Check pod events
kubectl describe pod <pod-name> -n trading

# Check pod logs
kubectl logs <pod-name> -n trading --previous
```

#### 2. Database Connection Issues
```bash
# Check database connectivity
kubectl exec -n trading deployment/api -- nc -zv postgres-server 5432

# Check database logs
kubectl logs -n trading deployment/api | grep -i database
```

#### 3. Redis Connection Issues
```bash
# Check Redis connectivity
kubectl exec -n trading deployment/api -- nc -zv redis-server 6379

# Check Redis logs
kubectl logs -n trading deployment/api | grep -i redis
```

#### 4. IB Gateway Connection Issues
```bash
# Check IB Gateway connectivity
kubectl exec -n trading deployment/md-collector -- nc -zv ib-gateway 7497

# Check IB Gateway logs
kubectl logs -n trading deployment/ib-gateway
```

### 5. Network Issues
```bash
# Check network policies
kubectl get networkpolicies -n trading

# Check service endpoints
kubectl get endpoints -n trading
```

## Maintenance

### 1. Regular Updates
```bash
# Update container images
docker build -t $ACR_NAME.azurecr.io/ib-gateway:latest apps/ib_gw/
docker push $ACR_NAME.azurecr.io/ib-gateway:latest

# Update deployments
kubectl set image deployment/ib-gateway ib-gateway=$ACR_NAME.azurecr.io/ib-gateway:latest -n trading
```

### 2. Database Maintenance
```bash
# Run database maintenance
kubectl exec -n trading deployment/api -- python -c "
import asyncio
import asyncpg
async def maintenance():
    conn = await asyncpg.connect('postgresql://...')
    await conn.execute('VACUUM ANALYZE')
    await conn.close()
asyncio.run(maintenance())
"
```

### 3. Log Rotation
```bash
# Configure log rotation
kubectl apply -f ops/logging/log-rotation.yaml
```

## Security Considerations

### 1. Access Control
- Use RBAC for Kubernetes access
- Implement network policies
- Use Azure AD integration

### 2. Secrets Management
- Use Azure Key Vault
- Implement secret rotation
- Monitor secret access

### 3. Network Security
- Use private endpoints
- Implement network segmentation
- Monitor network traffic

### 4. Data Protection
- Encrypt data at rest
- Encrypt data in transit
- Implement backup procedures

## Performance Optimization

### 1. Resource Optimization
- Right-size containers
- Implement horizontal pod autoscaling
- Use node affinity and anti-affinity

### 2. Database Optimization
- Implement connection pooling
- Use read replicas
- Optimize queries

### 3. Network Optimization
- Use service mesh
- Implement load balancing
- Optimize network policies

### 4. Monitoring Optimization
- Implement distributed tracing
- Use structured logging
- Optimize metrics collection
