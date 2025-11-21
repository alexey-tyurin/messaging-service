#!/bin/bash

# Test script for complete message flow through Redis queues
# This script tests the 8-step flow described in QUICK_START.md

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Message Flow Integration Test${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Check if Python script dependencies are installed
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import httpx, redis, rich" 2>/dev/null || {
    echo -e "${YELLOW}Installing required dependencies...${NC}"
    pip3 install httpx redis rich 2>/dev/null || {
        echo -e "${RED}Failed to install dependencies. Please run:${NC}"
        echo "  pip3 install httpx redis rich"
        exit 1
    }
}
echo -e "${GREEN}✓ Dependencies OK${NC}"
echo ""

# Check if services are running
echo -e "${YELLOW}Checking services...${NC}"

# Check API
if ! curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${RED}✗ API is not running at http://localhost:8080${NC}"
    echo "  Start with: make run-bg"
    exit 1
fi
echo -e "${GREEN}✓ API is running${NC}"

# Check Redis
if ! redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo -e "${RED}✗ Redis is not running${NC}"
    echo "  Start with: docker compose up -d redis"
    exit 1
fi
echo -e "${GREEN}✓ Redis is running${NC}"

# Check if worker is running (optional warning)
if ! pgrep -f "app.workers.message_processor" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Worker may not be running${NC}"
    echo "  For full flow testing, start worker with: make worker"
    echo "  (Tests will still run but may timeout on worker processing steps)"
    echo ""
fi

echo ""
echo -e "${BLUE}Running message flow tests...${NC}"
echo ""

# Run the Python test script
python3 "$(dirname "$0")/test_message_flow.py"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}Message Flow Tests Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
else
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}Some tests failed or timed out${NC}"
    echo -e "${RED}=========================================${NC}"
fi

echo ""
echo "Additional commands:"
echo "  make worker          - Start background worker"
echo "  make app-logs        - View application logs"
echo "  make redis-cli       - Access Redis CLI"
echo "  make db-shell        - Access PostgreSQL shell"
echo ""

exit $EXIT_CODE

