#!/bin/bash

# IBC startup script

set -e

echo "Starting IBC..."

# Set environment variables
export IBC_INI=/app/ibc/config.ini
export TWS_PATH=/app/tws
export TWS_SETTINGS_PATH=/app/tws/settings

# Create directories
mkdir -p /app/logs
mkdir -p /app/tws/settings

# Start IBC
exec /app/ibc/ibcstart.sh
