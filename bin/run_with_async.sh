#!/bin/bash
# Helper script to run the app with async processing enabled

echo "Starting Messaging Service with ASYNC processing mode..."
echo "=================================================="

# Set environment variable
export SYNC_MESSAGE_PROCESSING=false

# Stop any running instances
echo "Stopping any running instances..."
./bin/stop.sh

# Wait a moment
sleep 2

# Start the API server in background
echo "Starting API server..."
mkdir -p logs
nohup ./bin/start.sh > logs/app.log 2>&1 & echo $! > .app.pid
sleep 3

# Check if started
if [ -f .app.pid ]; then
    PID=$(cat .app.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✓ API started successfully (PID: $PID)"
        echo "  API: http://localhost:8080"
        echo "  Docs: http://localhost:8080/docs"
        echo "  Logs: tail -f logs/app.log"
    else
        echo "✗ API failed to start. Check logs/app.log"
        tail -20 logs/app.log
        exit 1
    fi
fi

echo ""
echo "Now start the worker in another terminal:"
echo "  make worker"
echo ""
echo "Then verify:"
echo "  make verify-redis-queue"

