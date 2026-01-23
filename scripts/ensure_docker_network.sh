#!/usr/bin/env bash
# ===========================================
# Ensure Docker Network Exists
# ===========================================
# This script ensures the external Docker network exists before running docker compose.
# It prevents deployment failures when the network doesn't exist.
#
# Usage:
#   ./scripts/ensure_docker_network.sh
#
# With custom network name:
#   DOCKER_NETWORK_NAME=custom-net ./scripts/ensure_docker_network.sh
#
# ===========================================

set -euo pipefail

NETWORK_NAME="${DOCKER_NETWORK_NAME:-prosaas-net}"

# Check if network exists
if docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
  echo "✅ Docker network exists: $NETWORK_NAME"
  exit 0
fi

# Create network if it doesn't exist
echo "🔧 Creating docker network: $NETWORK_NAME"
docker network create "$NETWORK_NAME" >/dev/null
echo "✅ Created: $NETWORK_NAME"
