<p align="center">
  <img src="docs/figures/figure_01_system_architecture.png" width="100%" />
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-0ea5e9?style=for-the-badge&logo=python&logoColor=white" /></a>
  <a href="https://azure.microsoft.com/"><img src="https://img.shields.io/badge/Azure-AKS-0f766e?style=for-the-badge&logo=microsoft-azure&logoColor=white" /></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Containerized-0891b2?style=for-the-badge&logo=docker&logoColor=white" /></a>
  <a href="https://www.terraform.io/"><img src="https://img.shields.io/badge/Terraform-IaC-7c3aed?style=for-the-badge&logo=terraform&logoColor=white" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-16a34a?style=for-the-badge" /></a>
  <a href="#tests"><img src="https://img.shields.io/badge/Tests-GitHub%20Actions-4b5563?style=for-the-badge&logo=githubactions&logoColor=white" /></a>
</p>

<p align="center">
  <h2 align="center">Azure-Deployed Interactive Brokers HFT</h2>
  <p align="center"><i>Production-grade infrastructure for low-latency, high-throughput trading on Interactive Brokers, deployed on Azure AKS.</i></p>
</p>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#key-features">Key Features</a> ·
  <a href="#system-architecture">System Architecture</a> ·
  <a href="#deployment">Deployment</a> ·
  <a href="#monitoring--observability">Monitoring</a> ·
  <a href="#getting-started">Getting Started</a> ·
  <a href="#roadmap">Roadmap</a>
</p>

---

### Overview

This repository provides a **production-focused infrastructure blueprint** for running a low-latency, Azure-hosted high-frequency trading (HFT) system on top of the **Interactive Brokers API**. It is designed as a modular platform that separates **data ingestion, signal generation, risk management, and order routing** into independently deployable services. The system targets **sub-100ms signal-to-order latency**, sustained **10K+ ticks/sec** market data throughput, and end-to-end observability across compute, network, and application layers. Infrastructure is provisioned via **Terraform**, containerized with **Docker**, and orchestrated on **Azure AKS**.

| Stage              | Description                                                                                  | Representative Tech                          |
|--------------------|----------------------------------------------------------------------------------------------|----------------------------------------------|
| Data Ingestion     | Stream high-volume ticks from IB Gateway into Redis Streams and TimescaleDB                 | IB API, Redis Streams, TimescaleDB           |
| Signal Generation  | Strategy logic consuming normalized feeds and emitting actionable trading signals           | Python, FastAPI, AKS                         |
| Risk Management    | Pre-trade and real-time checks enforcing exposure, limits, and safety rails                 | Risk/OMS microservice, Redis, Postgres       |
| Order Execution    | Low-latency, fault-aware order routing back to IB                                          | IB Gateway, Event Hubs (Kafka), FastAPI      |
| Monitoring         | Metrics, logs, and traces with alerting and runbook-driven escalation                      | Prometheus, Grafana, OpenTelemetry, AppInsights |

---

### Key Features

- **Azure-native HFT stack** – AKS, Redis Cache, PostgreSQL/TimescaleDB, Event Hubs, Key Vault, Application Insights.
- **Interactive Brokers integration** – Resilient connectivity to IB Gateway for market data and order routing.
- **Low-latency pipeline** – Data ingestion <5ms, risk checks <10ms, order processing <50ms, signal generation <100ms.
- **High-throughput streaming** – 10K+ ticks/sec, 1K+ orders/sec, 100+ signals/sec, 1M+ data points/min.
- **Defense-in-depth risk** – Pre-trade limits, real-time monitoring, emergency kill-switch and circuit breakers.
- **Full IaC** – Terraform-managed infrastructure and Kubernetes manifests for reproducible environments.
- **Observability by design** – Prometheus/Grafana dashboards, OpenTelemetry traces, and Azure-native monitoring.
- **Environment progression** – Backtest → Paper → Shadow-Live → Production deployment pipeline.

---

### System Architecture

<p align="center">
  <img src="docs/figures/figure_01_system_architecture.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 1 – System Architecture:</b> IB Gateway, market data and strategy services, Redis Streams, TimescaleDB, risk/OMS, and order routing on AKS with Azure managed services.</sub></p>

At the core of the system is an **AKS cluster** hosting microservices for **market data collection**, **strategy execution**, **risk/OMS**, and **API gateways**. Market data flows from **IB Gateway → Market Data Collector → Redis Streams → TimescaleDB**, while trading decisions propagate through **Strategy Engine → Risk/OMS → Event Hubs/Kafka → Order Execution**. Azure Key Vault centralizes secrets, Event Hubs handles streaming integrations, and Application Insights provides deep application telemetry alongside Prometheus and Grafana.

---

### Core Components

#### Market Data Processing (with Throughput Metrics)

<p align="center">
  <img src="docs/figures/figure_03_throughput_metrics.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 3 – Throughput Dashboard:</b> Sustained capacity across market data, orders, signals, and time-series storage.</sub></p>

- Normalizes and enriches real-time ticks from **Interactive Brokers**.
- Publishes structured streams into **Redis Streams** and archives into **TimescaleDB** for research and monitoring.
- Designed to handle **10K+ ticks/sec** with backpressure-aware publishers and consumers across `apps/` and `libs/`.

#### Signal Generation Engine

- Strategy services in `apps/` consume normalized market data and account state.
- Runs on **AKS** as horizontally scalable deployments, fronted by an internal API layer (FastAPI).
- Targets **sub-100ms** signal generation bounded by strict latency SLOs.

#### Risk Management System (with Layered Framework)

<p align="center">
  <img src="docs/figures/figure_05_risk_framework.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 5 – Risk Management Framework:</b> Pre-trade, real-time monitoring, and emergency controls in concentric layers.</sub></p>

- **Pre-Trade Risk** – Position and exposure limits, per-instrument/order size limits, and rate-limiting before orders are routed.
- **Real-Time Monitoring** – P&L drift, volatility regime changes, and latency anomalies feeding back into controls and alerts.
- **Emergency Controls** – Global kill switch, strategy-level circuit breakers, and fast de-risking workflows.

#### Order Management System

- Consolidates **order state**, **fills**, and **positions** with TimescaleDB-backed storage.
- Interacts with **Event Hubs (Kafka)** for event-driven integrations and replayable order streams.
- Encapsulates exchange/broker-specific concerns away from strategy code, enabling safer iteration in `apps/` and `infra/`.

---

### Performance

<p align="center">
  <img src="docs/figures/figure_02_latency_waterfall.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 2 – Latency Waterfall:</b> Stage-level latency budgets across the trading pipeline.</sub></p>

<p align="center">
  <img src="docs/figures/figure_03_throughput_metrics.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 3 – Throughput Dashboard:</b> Capacity envelopes for data ingestion, order flow, signals, and storage.</sub></p>

| Dimension           | Target / Envelope                               |
|---------------------|--------------------------------------------------|
| Data Ingestion      | < 5 ms tick-to-cache, 10K+ ticks/sec           |
| Risk Checks         | < 10 ms per order                              |
| Order Processing    | < 50 ms broker round-trip (excluding venue)    |
| Signal Generation   | < 100 ms from tick to signal emission          |
| Order Throughput    | 1K+ orders/sec sustained                         |
| Signal Throughput   | 100+ signals/sec                                 |
| Storage Throughput  | 1M+ data points/min into TimescaleDB            |

Latency and throughput characteristics are enforced via **service-level objectives (SLOs)**, autoscaling policies, and metric-driven alerting.

---

### Deployment

<p align="center">
  <img src="docs/figures/figure_04_deployment_pipeline.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 4 – Deployment Pipeline:</b> Backtest → Paper → Shadow-Live → Production with validation gates and tooling overlays.</sub></p>

<p align="center">
  <img src="docs/figures/figure_06_azure_infrastructure.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 6 – Azure Infrastructure Map:</b> AKS, PostgreSQL/TimescaleDB, Redis Cache, Event Hubs, Key Vault, and Application Insights within secure VNets.</sub></p>

Core tooling:

- **Terraform (`infra/`)** – Provisions AKS, PostgreSQL/TimescaleDB, Redis Cache, Event Hubs, VNets, NSGs, and Key Vault.
- **Docker (`apps/`, `libs/`)** – Builds container images for strategy, data, and risk services.
- **Kubernetes (`ops/`)** – Manifests/Helm charts for deployments, services, HPAs, and config.

Typical workflow using the provided `Makefile`:

```bash
# 1. Bootstrap local/dev environment
make env            # copy .env.sample -> .env and validate basics
make venv           # create Python virtual environment
make install        # install Python dependencies via pyproject.toml

# 2. Build and test containers
make docker-build   # build all service images
make test           # run unit/integration tests in tests/

# 3. Provision Azure infrastructure
make terraform-init
make terraform-plan
make terraform-apply

# 4. Deploy to AKS
make kube-apply     # apply manifests / Helm charts
make kube-status    # verify deployments and services

# 5. Tear down (non-prod)
make terraform-destroy
```

---

### Monitoring & Observability

<p align="center">
  <img src="docs/figures/figure_08_monitoring_stack.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 8 – Monitoring & Observability Stack:</b> OpenTelemetry instrumentation, Prometheus scraping, Grafana dashboards, and App Insights-backed traces and alerts.</sub></p>

The stack is built around:

- **OpenTelemetry** for consistent tracing and metrics across **Python services**.
- **Prometheus** for metrics collection from AKS workloads and infrastructure exporters.
- **Grafana** for operator and trader-facing dashboards (latency, throughput, risk posture).
- **Application Insights** for distributed tracing, logs, and queryable telemetry.
- **Alert rules** wired into on-call channels for latency breaches, risk limit violations, and infra failures.

---

### Trade Lifecycle

<p align="center">
  <img src="docs/figures/figure_07_data_flow.png" width="100%" />
</p>
<p align="center"><sub><b>Figure 7 – Data Flow Timeline:</b> Single trade lifecycle from tick ingestion through P&amp;L reconciliation.</sub></p>

A typical end-to-end lifecycle:

1. **Market tick arrives** from Interactive Brokers and is ingested by the **Market Data Collector**.
2. Tick is **cached in Redis** and normalized, while being **persisted to TimescaleDB** for analytics.
3. **Signal Generation Engine** consumes recent state and emits trade signals under strict latency budgets.
4. **Risk/OMS** performs **pre-trade validation** (limits, exposure, rate checks) and enriches the order.
5. Validated orders are **submitted to IB** via the order execution service and **routed via Event Hubs** if needed.
6. Fills are **received and matched**, positions are updated, and **P&L is reconciled** and persisted.
7. Throughout, **metrics, logs, and traces** are emitted to Prometheus and Application Insights.

---

### Security

| Control Area          | Mechanism                                                                                         |
|-----------------------|---------------------------------------------------------------------------------------------------|
| Secrets Management    | All sensitive config stored in **Azure Key Vault**, referenced by AKS-managed identities.        |
| Network Isolation     | Workloads hosted inside **VNets** with NSGs and **private endpoints** for databases and caches.  |
| Authentication        | Service-to-service auth via **managed identities** and scoped tokens.                            |
| Risk Controls         | **Pre-trade validation**, **position/exposure limits**, and **rate limiting** enforced in OMS.   |
| Kill Switch           | Dedicated **global kill switch** and **strategy-level circuit breakers** wired into deployment.  |
| Auditability          | Orders, fills, and risk decisions logged with **immutable event streams** (Event Hubs + DB).     |

> This repository focuses on **infrastructure patterns and building blocks**. You are responsible for configuring production-grade policies, permissions, and compliance controls appropriate to your environment.

---

### Configuration

<details>
<summary><b>Click to expand configuration and environment details</b></summary>

#### Environment Variables

Configuration is primarily driven via `.env` (see `.env.sample`) and Kubernetes `Secret`/`ConfigMap` resources.

Typical variables include (non-exhaustive):

| Variable                       | Description                                           |
|--------------------------------|-------------------------------------------------------|
| `IB_GATEWAY_HOST`             | Hostname/IP of the Interactive Brokers gateway        |
| `IB_GATEWAY_PORT`             | Port for TWS/Gateway API                             |
| `REDIS_URL`                   | Redis Streams connection string                       |
| `POSTGRES_URL`                | PostgreSQL/TimescaleDB connection string             |
| `KAFKA_BROKERS` / `EVENT_HUB` | Kafka/Event Hubs bootstrap servers                    |
| `OTEL_EXPORTER_ENDPOINT`      | OpenTelemetry collector endpoint                      |
| `APPINSIGHTS_CONNECTION_STRING` | Azure Application Insights connection string       |
| `RISK_LIMITS_CONFIG`          | Path or key for risk limit configuration             |

Secrets such as API keys and connection strings should not be stored in Git; use Key Vault-backed references.

#### Azure Key Vault Setup

- Create a dedicated **Key Vault** for this HFT stack.
- Configure **AKS managed identity** to have `get`/`list` permissions on secrets and certificates.
- Store critical values (broker credentials, DB passwords, Redis keys, telemetry secrets) in Key Vault.
- Reference Key Vault secrets via:
  - Terraform data sources and AKS add-ons, or
  - CSI secret store driver for Kubernetes-mounted secrets.

</details>

---

### Getting Started

#### Prerequisites

- **Azure subscription** with permissions to create AKS, Redis Cache, PostgreSQL/TimescaleDB, Event Hubs, and Key Vault.
- **Python 3.11+**
- **Docker** and **kubectl**
- **Terraform** (recommended: latest stable)
- Access to an **Interactive Brokers** paper/production account and gateway.

#### 1. Clone the Repository

```bash
git clone https://github.com/FelipeCardozo0/Azure-Deployed-Interactive-Brokers-HFT.git
cd Azure-Deployed-Interactive-Brokers-HFT
```

#### 2. Configure Environment

```bash
cp .env.sample .env
# Edit .env with your IB, Redis, Postgres, Event Hubs, and Azure configuration
```

#### 3. Set Up Python Environment

```bash
make venv
source .venv/bin/activate
make install
```

#### 4. Generate Documentation Figures (Optional but Recommended)

```bash
# From the repo root (assuming Jupyter installed via pyproject.toml)
jupyter nbconvert --to notebook --execute notebooks/visualization.ipynb
# or open notebooks/visualization.ipynb and run all cells in your IDE
```

#### 5. Provision Azure Infrastructure

```bash
make terraform-init
make terraform-plan
make terraform-apply
```

#### 6. Deploy to AKS

```bash
make docker-build
make kube-apply
make kube-status
```

#### 7. Run Tests

```bash
make test
```

---

### Limitations & Disclaimer

This project is provided **for educational and infrastructure reference purposes only** and does **not** constitute trading advice or a complete production trading platform. Real-world HFT deployments require extensive **latency benchmarking**, **venue-specific tuning**, **operational hardening**, and **regulatory/compliance reviews** that are outside the scope of this repository. Latency and throughput numbers referenced here are **targets**, not guarantees; your results will vary based on hardware, network, and broker conditions. You are solely responsible for any financial risk associated with using or adapting this code.

---

### Roadmap

- [ ] Harden CI/CD pipeline with canary deployments and automated rollbacks.
- [ ] Expand monitoring dashboards with per-strategy latency, hit ratios, and risk utilization.
- [ ] Add sample strategies for backtesting and paper trading across multiple instruments.
- [ ] Integrate additional brokers/exchanges behind a unified OMS abstraction.
- [ ] Implement full-blown chaos testing for broker/API and market data failure modes.
- [ ] Publish Helm charts for one-command AKS deployment.
- [ ] Provide reference runbooks for common operational incidents.

---

### Repository Layout

| Path       | Description                                              |
|-----------|----------------------------------------------------------|
| `apps/`   | Application services (market data, strategies, risk, OMS) |
| `libs/`   | Shared Python libraries and utilities                     |
| `infra/`  | Terraform modules and cloud infrastructure definitions    |
| `ops/`    | Kubernetes manifests, Helm charts, and operational assets |
| `tests/`  | Unit and integration tests                                |
| `docs/`   | Documentation assets (including generated figures)        |

---

### Footer

<p align="center">
  Built and maintained by <a href="https://github.com/FelipeCardozo0">Felipe Cardozo</a>.<br/>
  <sub>Use responsibly. Markets move fast; production changes should move slower.</sub>
</p>
