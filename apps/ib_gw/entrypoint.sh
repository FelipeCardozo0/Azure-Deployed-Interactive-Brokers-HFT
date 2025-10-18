#!/bin/bash

# IB Gateway entrypoint script

set -e

echo "Starting IB Gateway container..."

# Set environment variables
export DISPLAY=:99
export IB_GATEWAY_PORT=${IB_GATEWAY_PORT:-7497}
export IB_GATEWAY_HOST=${IB_GATEWAY_HOST:-0.0.0.0}

# Start Xvfb
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for Xvfb to start
sleep 2

# Start fluxbox window manager
echo "Starting fluxbox..."
fluxbox &
FLUXBOX_PID=$!

# Wait for fluxbox to start
sleep 2

# Start IBC
echo "Starting IBC..."
cd /app/ibc
./start.sh &
IBC_PID=$!

# Wait for IBC to start
sleep 10

# Check if IB Gateway is running
echo "Checking IB Gateway status..."
for i in {1..30}; do
    if netstat -ln | grep -q ":${IB_GATEWAY_PORT}"; then
        echo "IB Gateway is running on port ${IB_GATEWAY_PORT}"
        break
    fi
    echo "Waiting for IB Gateway to start... (${i}/30)"
    sleep 2
done

# Check if IB Gateway is accessible
if ! netstat -ln | grep -q ":${IB_GATEWAY_PORT}"; then
    echo "ERROR: IB Gateway failed to start on port ${IB_GATEWAY_PORT}"
    exit 1
fi

echo "IB Gateway container started successfully"

# Keep container running
wait
