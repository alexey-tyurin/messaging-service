# Setup Instructions - Important!

## Quick Start

### 1. Activate Your Python Environment

**Before running the application**, you must activate your conda environment:

```bash
conda activate py311
```

Or if using a virtual environment:

```bash
source venv/bin/activate
```

### 2. Ensure Docker Services are Running

Make sure PostgreSQL and Redis are running:

```bash
docker compose up -d postgres redis
```

Verify they're healthy:

```bash
docker compose ps
```

You should see both services with status "Up" and "(healthy)".

### 3. Run the Application

```bash
make run
```

Or directly:

```bash
./bin/start.sh
```

The application will:
- ✅ Detect your conda/virtual environment
- ✅ Check PostgreSQL and Redis connectivity  
- ✅ Run database migrations
- ✅ Start the FastAPI server on http://localhost:8080

## Troubleshooting

### Error: "FastAPI not found in Python environment"

**Problem**: The system Python doesn't have the required packages.

**Solution**: Activate your conda environment first:

```bash
conda activate py311
make run
```

### Error: "PostgreSQL is not available"

**Problem**: PostgreSQL container is not running or not accessible.

**Solutions**:
1. Check if containers are running: `docker compose ps`
2. Start PostgreSQL: `docker compose up -d postgres`
3. Check port 5432 is not in use: `lsof -i :5432`

### Error: "Redis is not available"  

**Problem**: Redis container is not running or not accessible.

**Solutions**:
1. Start Redis: `docker compose up -d redis`
2. Check port 6379 is not in use: `lsof -i :6379`

## Environment Variables

The application uses environment variables for configuration. Key variables:

- `POSTGRES_HOST=localhost` - PostgreSQL host (default: localhost)
- `POSTGRES_PORT=5432` - PostgreSQL port
- `POSTGRES_USER=messaging_user` - Database user  
- `POSTGRES_PASSWORD=messaging_password` - Database password
- `POSTGRES_DB=messaging_service` - Database name
- `REDIS_HOST=localhost` - Redis host
- `REDIS_PORT=6379` - Redis port

These are automatically set by the startup script when running locally.

## Next Steps

Once the application is running:

1. **API Documentation**: http://localhost:8080/docs
2. **Health Check**: http://localhost:8080/health
3. **Metrics**: http://localhost:8080/metrics
4. **Prometheus**: http://localhost:9090
5. **Grafana**: http://localhost:3000 (admin/admin)

## Development Commands

```bash
make run          # Start API server
make worker       # Start background worker
make test         # Run tests
make lint         # Check code quality
make migrate      # Run database migrations
```

## Production Deployment

For production deployment, see [ARCHITECTURE.md](./ARCHITECTURE.md) and use:

```bash
docker compose up -d
```

This will start all services including the app and worker in containers.

