# Quick Start/Stop Guide

## 🚀 Starting the Application

### Method 1: Using Make (Recommended)

```bash
# First, activate your conda environment
conda activate py311

# Then start the service
make run
```

### Method 2: Direct Script

```bash
conda activate py311
./bin/start.sh
```

The application will start on **http://localhost:8000**

Available endpoints:
- 📚 **API Docs**: http://localhost:8000/docs
- 💚 **Health Check**: http://localhost:8000/health
- 📊 **Metrics**: http://localhost:8000/metrics

## 🛑 Stopping the Application

### Method 1: Using Make (Recommended)

```bash
make stop
```

### Method 2: Direct Script

```bash
./bin/stop.sh
```

This will:
- ✅ Kill all processes on port 8000
- ✅ Stop uvicorn processes
- ✅ Stop worker processes
- ✅ Stop gunicorn processes (if any)

## 🔄 Restarting the Application

```bash
make restart
```

This will:
1. Stop all running services
2. Wait 2 seconds
3. Start the application again

## ⚠️ Troubleshooting

### Error: "Address already in use" (Port 8000)

**Solution**: Stop existing services first

```bash
make stop
make run
```

### Error: "This site can't be reached"

**Possible causes:**
1. Application is not running
2. Application failed to start
3. Wrong conda environment

**Solutions:**

1. **Check if running:**
```bash
lsof -i:8000
```

2. **Activate correct environment:**
```bash
conda activate py311
make run
```

3. **Check Docker services:**
```bash
docker compose ps
```

Make sure PostgreSQL and Redis are running (status: "Up (healthy)")

4. **View startup logs:**
The startup script shows real-time output. Look for errors.

### Error: "PostgreSQL is not available"

```bash
# Start PostgreSQL
docker compose up -d postgres

# Check status
docker compose ps postgres

# View logs if there's an issue
docker compose logs postgres
```

### Error: "Redis is not available"

```bash
# Start Redis
docker compose up -d redis

# Check status
docker compose ps redis
```

## 🐳 Docker Services Management

### Start all Docker services (PostgreSQL, Redis, Prometheus, Grafana)

```bash
make docker-up
```

Or:

```bash
docker compose up -d
```

### Stop all Docker services

```bash
make docker-down
```

Or:

```bash
docker compose down
```

### View Docker logs

```bash
make docker-logs
```

Or for specific service:

```bash
docker compose logs -f postgres
docker compose logs -f redis
```

## 📋 Common Command Reference

| Command | Description |
|---------|-------------|
| `make run` | Start the application |
| `make stop` | Stop all services |
| `make restart` | Restart the application |
| `make worker` | Start background worker |
| `make test` | Run tests |
| `make migrate` | Run database migrations |
| `make docker-up` | Start Docker containers |
| `make docker-down` | Stop Docker containers |
| `make clean` | Clean generated files |

## 🔍 Checking Service Status

### Check if app is running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "..."
}
```

### Check what's using port 8000

```bash
lsof -i:8000
```

### Check all running services

```bash
# Docker services
docker compose ps

# Local Python processes
ps aux | grep -E "uvicorn|gunicorn|message_processor"
```

## 💡 Tips

1. **Always activate conda environment first**: `conda activate py311`
2. **Use `make stop` before restarting** to avoid "Address in use" errors
3. **Check Docker services are healthy** before starting the app
4. **Use `make restart`** for quick restarts during development

## 🆘 Emergency Stop

If `make stop` doesn't work, manually kill processes:

```bash
# Kill everything on port 8000
kill -9 $(lsof -ti:8000)

# Or stop all Python services
pkill -f "uvicorn|app.main"
```

## 📞 Need Help?

Check the logs and documentation:
- [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md) - Initial setup guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [PRD.md](./PRD.md) - Product requirements

