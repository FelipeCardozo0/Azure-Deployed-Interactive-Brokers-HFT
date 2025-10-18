# IB Gateway Dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    xvfb \
    x11vnc \
    fluxbox \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy IBC files
COPY ibc/ /app/ibc/
RUN chmod +x /app/ibc/start.sh

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create supervisor config
RUN mkdir -p /var/log/supervisor
COPY supervisor.conf /etc/supervisor/conf.d/supervisor.conf

# Expose ports
EXPOSE 7497 5900

# Set environment variables
ENV DISPLAY=:99
ENV IB_GATEWAY_PORT=7497
ENV IB_GATEWAY_HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7497/health || exit 1

# Start supervisor
CMD ["/app/entrypoint.sh"]
