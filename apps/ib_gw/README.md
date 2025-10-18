# IB Gateway Container

This container runs Interactive Brokers Gateway in headless mode for automated trading.

## Prerequisites

- Interactive Brokers account
- TWS API credentials
- Acceptance of IBKR Terms of Service (must be done locally first)

## Configuration

The container uses IBC (Interactive Brokers Controller) to manage the Gateway.

### Environment Variables

- `IB_GATEWAY_PORT`: Gateway port (default: 7497)
- `IB_GATEWAY_HOST`: Gateway host (default: 0.0.0.0)
- `TWS_USERID`: IBKR username
- `TWS_PASSWORD`: IBKR password
- `TWS_ACCOUNT`: IBKR account number

### Secrets

Credentials are provided via Azure Key Vault and mounted as environment variables.

## Usage

```bash
# Build the image
docker build -t hft-ib-azure/ib-gateway:latest .

# Run the container
docker run -d \
  --name ib-gateway \
  -p 7497:7497 \
  -e TWS_USERID=your_username \
  -e TWS_PASSWORD=your_password \
  -e TWS_ACCOUNT=your_account \
  hft-ib-azure/ib-gateway:latest
```

## Health Check

The container exposes a health check endpoint at `http://localhost:7497/health`.

## Logs

Logs are written to `/app/logs` inside the container.

## Security

- No credentials are hardcoded in the image
- All secrets are provided via environment variables
- The container runs as a non-root user
- Network access is restricted to necessary ports only
