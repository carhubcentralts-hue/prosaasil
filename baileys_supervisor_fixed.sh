#!/bin/bash
set -e

echo "🚀 Starting ROBUST Baileys Supervisor..."

# Environment setup
export PORT=5000
export BAILEYS_PORT=3310
export WHATSAPP_PROVIDER=baileys

# Supervisor settings (Architect recommendations)
HEALTH_TIMEOUT=6s
FAIL_THRESHOLD=3
STARTUP_GRACE=15
consecutive_failures=0
startup_time=$(date +%s)

cleanup() {
    echo "🛑 Supervisor cleanup..."
    if [ -f baileys.pid ]; then
        PID=$(cat baileys.pid)
        kill $PID 2>/dev/null || true
        rm -f baileys.pid
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

wait_for_port_close() {
    echo "⏳ Waiting for port 3310 to close..."
    for i in {1..10}; do
        if ! curl -s --max-time 1 http://127.0.0.1:3310/healthz > /dev/null 2>&1; then
            echo "✅ Port 3310 is free"
            return 0
        fi
        echo "⏳ Port still busy, waiting..."
        sleep 2
    done
    echo "⚠️ Port still busy after 20s, proceeding anyway"
}

start_baileys() {
    echo "📱 Starting Baileys service..."
    cd services/baileys
    npm install &> /dev/null || true
    nohup node server.js > ../../baileys_service.log 2>&1 &
    BAILEYS_PID=$!
    echo $BAILEYS_PID > ../../baileys.pid
    cd ../..
    echo "✅ Baileys started with PID: $BAILEYS_PID"
    consecutive_failures=0
    startup_time=$(date +%s)
}

health_check() {
    curl -s --max-time $HEALTH_TIMEOUT http://127.0.0.1:3310/healthz > /dev/null 2>&1
}

should_restart() {
    current_time=$(date +%s)
    uptime=$((current_time - startup_time))
    
    # Startup grace period
    if [ $uptime -lt $STARTUP_GRACE ]; then
        echo "🚼 Startup grace period (${uptime}s < ${STARTUP_GRACE}s), ignoring failure"
        return 1
    fi
    
    # Check consecutive failures
    if [ $consecutive_failures -ge $FAIL_THRESHOLD ]; then
        echo "💥 $consecutive_failures consecutive failures >= $FAIL_THRESHOLD, restart needed"
        return 0
    fi
    
    return 1
}

# Start Baileys initially
start_baileys

# Infinite monitoring loop
COUNTER=0
while true; do
    sleep 5
    COUNTER=$((COUNTER + 1))
    
    # Check if process exists
    if [ -f baileys.pid ]; then
        PID=$(cat baileys.pid)
        if ! kill -0 $PID 2>/dev/null; then
            echo "❌ Baileys process died (PID $PID)"
            consecutive_failures=$((consecutive_failures + 1))
            if should_restart; then
                echo "🔄 Restarting after process death..."
                wait_for_port_close
                start_baileys
                continue
            fi
        fi
    else
        echo "❌ No PID file found"
        consecutive_failures=$((consecutive_failures + 1))
        if should_restart; then
            echo "🔄 Restarting after missing PID..."
            wait_for_port_close
            start_baileys
            continue
        fi
    fi
    
    # Health check with better error handling
    if health_check; then
        consecutive_failures=0
        if [ $((COUNTER % 24)) -eq 0 ]; then  # Every 2 minutes
            PID=$(cat baileys.pid 2>/dev/null || echo "NO-PID")
            uptime=$(($(date +%s) - startup_time))
            echo "💓 Supervisor: Baileys PID $PID, uptime ${uptime}s, 0 failures - $(date)"
        fi
    else
        consecutive_failures=$((consecutive_failures + 1))
        echo "⚠️ Health check failed ($consecutive_failures/$FAIL_THRESHOLD) - $(date)"
        
        if should_restart; then
            echo "🔄 Restarting after $consecutive_failures health failures..."
            if [ -f baileys.pid ]; then
                PID=$(cat baileys.pid)
                echo "📋 Last 5 lines of baileys_service.log:"
                tail -5 baileys_service.log || true
                kill $PID 2>/dev/null || true
            fi
            wait_for_port_close
            start_baileys
        fi
    fi
done