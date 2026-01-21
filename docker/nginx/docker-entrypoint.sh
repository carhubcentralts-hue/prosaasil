#!/bin/sh
#
# Nginx Entrypoint - Environment Variable Substitution
# 
# This script processes nginx config templates and replaces
# environment variables before nginx starts.
#
# Variables supported:
# - API_UPSTREAM: Service name for API endpoints (default: backend)
# - API_PORT: Port for API service (default: 5000)
# - CALLS_UPSTREAM: Service name for WebSocket/calls (default: backend)
# - CALLS_PORT: Port for calls service (default: 5000)
# - FRONTEND_UPSTREAM: Service name for frontend (default: frontend)

set -e

# Default values if not set
export API_UPSTREAM=${API_UPSTREAM:-backend}
export API_PORT=${API_PORT:-5000}
export CALLS_UPSTREAM=${CALLS_UPSTREAM:-backend}
export CALLS_PORT=${CALLS_PORT:-5000}
export FRONTEND_UPSTREAM=${FRONTEND_UPSTREAM:-frontend}

echo "=== Nginx Config Templating ==="
echo "API_UPSTREAM: ${API_UPSTREAM}:${API_PORT}"
echo "CALLS_UPSTREAM: ${CALLS_UPSTREAM}:${CALLS_PORT}"
echo "FRONTEND_UPSTREAM: ${FRONTEND_UPSTREAM}"

# Create conf.d directory if it doesn't exist
mkdir -p /etc/nginx/conf.d

# Process each template file
for template in /etc/nginx/templates/*.conf; do
    if [ -f "$template" ]; then
        filename=$(basename "$template")
        output="/etc/nginx/conf.d/${filename}"
        
        echo "Processing template: ${filename}"
        
        # Use envsubst to replace environment variables
        envsubst '${API_UPSTREAM} ${API_PORT} ${CALLS_UPSTREAM} ${CALLS_PORT} ${FRONTEND_UPSTREAM}' < "$template" > "$output"
        
        echo "  → Generated: ${output}"
    fi
done

echo "=== Template processing complete ==="
echo ""

# Continue with default nginx startup
exec "$@"
