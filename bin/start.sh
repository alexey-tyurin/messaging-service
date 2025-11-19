#!/bin/bash

# Start script for Messaging Service
set -e

echo "Starting Hatch Messaging Service..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo -e "${GREEN}Running in Docker container${NC}"
    POSTGRES_HOST=${POSTGRES_HOST:-postgres}
    REDIS_HOST=${REDIS_HOST:-redis}
else
    echo -e "${YELLOW}Running locally${NC}"
    POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    REDIS_HOST=${REDIS_HOST:-localhost}
fi

# Export environment variables
export POSTGRES_HOST
export REDIS_HOST

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -f /.dockerenv ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    if [ ! -f /.dockerenv ]; then
        source venv/bin/activate 2>/dev/null || true
    fi
fi

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
for i in {1..30}; do
    if python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='${POSTGRES_HOST}',
        port=5432,
        user='messaging_user',
        password='messaging_password',
        database='messaging_service'
    )
    conn.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}PostgreSQL is ready${NC}"
        break
    else
        if [ $i -eq 30 ]; then
            echo -e "${RED}PostgreSQL is not available${NC}"
            echo "Please ensure PostgreSQL is running with:"
            echo "  docker-compose up -d postgres"
            exit 1
        fi
        echo "Waiting for PostgreSQL... ($i/30)"
        sleep 2
    fi
done

# Check Redis connection
echo "Checking Redis connection..."
for i in {1..30}; do
    if python3 -c "
import redis
try:
    r = redis.Redis(host='${REDIS_HOST}', port=6379)
    r.ping()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}Redis is ready${NC}"
        break
    else
        if [ $i -eq 30 ]; then
            echo -e "${RED}Redis is not available${NC}"
            echo "Please ensure Redis is running with:"
            echo "  docker-compose up -d redis"
            exit 1
        fi
        echo "Waiting for Redis... ($i/30)"
        sleep 2
    fi
done

# Run database migrations
echo "Running database migrations..."
alembic upgrade head || {
    echo -e "${YELLOW}Failed to run migrations, attempting to initialize...${NC}"
    python3 -c "
from app.db.session import db_manager
import asyncio
async def init():
    db_manager.init_db()
    await db_manager.create_tables()
asyncio.run(init())
"
}

# Start the application
echo -e "${GREEN}Starting application on http://localhost:8000${NC}"
echo -e "${GREEN}API Documentation: http://localhost:8000/docs${NC}"
echo -e "${GREEN}Health Check: http://localhost:8000/health${NC}"

# Set number of workers based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    WORKERS=${WORKERS:-4}
    echo "Starting in production mode with $WORKERS workers..."
    exec gunicorn app.main:app \
        --workers $WORKERS \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --access-log - \
        --error-log - \
        --log-level info
else
    echo "Starting in development mode..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level debug
fi
