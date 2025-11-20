#!/bin/bash

# Stop script for Messaging Service
set -e

echo "Stopping Messaging Service..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to kill processes on a specific port
kill_port() {
    local port=$1
    local service_name=$2
    
    echo "Checking for processes on port $port ($service_name)..."
    
    # Find PIDs using the port
    PIDS=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}Found process(es) on port $port: $PIDS${NC}"
        for PID in $PIDS; do
            # Get process info
            PROC_INFO=$(ps -p $PID -o comm= 2>/dev/null || echo "unknown")
            echo "  Killing PID $PID ($PROC_INFO)..."
            kill -15 $PID 2>/dev/null || true
            
            # Wait a moment for graceful shutdown
            sleep 1
            
            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                echo "  Force killing PID $PID..."
                kill -9 $PID 2>/dev/null || true
            fi
        done
        echo -e "${GREEN}✓ Stopped $service_name${NC}"
    else
        echo -e "${GREEN}✓ No process found on port $port${NC}"
    fi
}

# Function to kill processes by name pattern
kill_by_pattern() {
    local pattern=$1
    local service_name=$2
    
    echo "Checking for $service_name processes..."
    
    # Find PIDs matching pattern
    PIDS=$(pgrep -f "$pattern" 2>/dev/null || true)
    
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}Found $service_name process(es): $PIDS${NC}"
        for PID in $PIDS; do
            PROC_INFO=$(ps -p $PID -o comm= 2>/dev/null || echo "unknown")
            echo "  Killing PID $PID ($PROC_INFO)..."
            kill -15 $PID 2>/dev/null || true
            sleep 1
            if ps -p $PID > /dev/null 2>&1; then
                kill -9 $PID 2>/dev/null || true
            fi
        done
        echo -e "${GREEN}✓ Stopped $service_name${NC}"
    else
        echo -e "${GREEN}✓ No $service_name processes found${NC}"
    fi
}

# Stop FastAPI application on port 8080
kill_port 8080 "FastAPI"

# Stop any uvicorn processes
kill_by_pattern "uvicorn.*app.main:app" "Uvicorn"

# Stop any worker processes
kill_by_pattern "app.workers.message_processor" "Message Worker"

# Stop any gunicorn processes (if running)
kill_by_pattern "gunicorn.*app.main:app" "Gunicorn"

# Optional: Stop Docker containers (commented out by default)
# Uncomment if you want to stop Docker services too
# echo ""
# echo "Stopping Docker services..."
# docker compose stop app worker 2>/dev/null || true

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}All services stopped!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "To start services again, run:"
echo "  make run"
echo ""
echo "To stop Docker services, run:"
echo "  docker compose down"

