# Running the Application - Quick Guide

## 🚀 Two Ways to Run

### Option 1: Background Mode (Recommended) ✅

Run the application in the background so you can continue using your terminal:

```bash
# Activate conda environment
conda activate py311

# Start in background
make run-bg
```

**Output:**
```
Starting application in background...
✓ Application started successfully in background (PID: 12345)
  View logs: tail -f logs/app.log
  Stop: make stop
```

You can now use your terminal for other commands! 🎉

### Option 2: Foreground Mode

Run the application in the foreground (blocks terminal):

```bash
# Activate conda environment
conda activate py311

# Start in foreground
make run
```

**Note:** This will block your terminal. To stop: press `Ctrl+C`

To use other commands, you'll need to open a new terminal window.

---

## 📋 Management Commands

### Check Status
```bash
make status
```

Output:
```
✓ Application is running (PID: 12345)
python3   12345 user   8u  IPv4  TCP *:8080 (LISTEN)
```

### View Logs (Background Mode)
```bash
make logs
```

Or manually:
```bash
tail -f logs/app.log
```

### Stop Application
```bash
make stop
```

### Restart Application
```bash
make restart
```

This will:
1. Stop the current instance
2. Wait 2 seconds
3. Start in background mode

---

## 🔧 Common Scenarios

### Scenario 1: Development with Hot Reload

**Use foreground mode in a dedicated terminal:**

Terminal 1 (Application):
```bash
conda activate py311
make run
```

Terminal 2 (Commands):
```bash
conda activate py311
curl http://localhost:8080/health
make test
```

### Scenario 2: Testing/Background Work

**Use background mode in a single terminal:**

```bash
conda activate py311
make run-bg

# Now you can run other commands
curl http://localhost:8080/health
make test

# View logs when needed
make logs

# Stop when done
make stop
```

### Scenario 3: Check What's Running

```bash
# Check application status
make status

# Check port 8080
lsof -i:8080

# Or with netstat
netstat -an | grep 8080
```

---

## 🐛 Troubleshooting

### Terminal is Blocked After `make run`

**Solutions:**

1. **Stop it:** Press `Ctrl+C` in the terminal
2. **Or open new terminal:** Keep the app running, use another terminal
3. **Or use background mode:** Stop with `Ctrl+C`, then run `make run-bg`

### Application Won't Stop

```bash
# Force stop all services
make stop

# If that doesn't work, kill manually
lsof -ti:8080 | xargs kill -9
```

### Can't Find Logs

```bash
# Check if logs directory exists
ls -la logs/

# If it doesn't exist
mkdir -p logs

# Then start in background mode
make run-bg
```

### Port Already in Use

```bash
# Stop existing services
make stop

# Check if anything is still running
lsof -i:8080

# Force kill if needed
lsof -ti:8080 | xargs kill -9

# Start again
make run-bg
```

---

## 📊 Monitoring

### Watch Logs in Real-Time
```bash
tail -f logs/app.log
```

### Check Health While Running
```bash
# In background mode, you can run:
curl http://localhost:8080/health

# Check all endpoints
curl http://localhost:8080/ready
curl http://localhost:8080/metrics
```

### Monitor Requests
```bash
# In foreground mode, you'll see requests in terminal
# In background mode, check logs:
tail -f logs/app.log | grep "Request"
```

---

## 💡 Pro Tips

1. **Use background mode for most development:**
   ```bash
   make run-bg && make logs
   ```

2. **Quick test after changes:**
   ```bash
   make restart && sleep 2 && curl http://localhost:8080/health
   ```

3. **Clean start:**
   ```bash
   make stop && make run-bg
   ```

4. **Multiple terminals approach:**
   - Terminal 1: `make run` (see live logs)
   - Terminal 2: Run commands and tests

5. **Check everything is working:**
   ```bash
   make status && curl http://localhost:8080/health
   ```

---

## 📝 Command Reference

| Command | Description | Blocks Terminal? |
|---------|-------------|------------------|
| `make run` | Run in foreground | ✅ Yes |
| `make run-bg` | Run in background | ❌ No |
| `make stop` | Stop application | ❌ No |
| `make restart` | Restart (background) | ❌ No |
| `make status` | Check status | ❌ No |
| `make logs` | View logs | ✅ Yes (until Ctrl+C) |
| `make test` | Run tests | ✅ Yes (until complete) |

---

## 🎯 Recommended Workflow

```bash
# 1. Start services
conda activate py311
docker compose up -d postgres redis

# 2. Run application in background
make run-bg

# 3. Verify it's working
make status
curl http://localhost:8080/health

# 4. Do your work (all in same terminal!)
make test
curl http://localhost:8080/api/v1/messages/

# 5. Check logs if needed
make logs  # Press Ctrl+C to exit

# 6. Stop when done
make stop
```

This workflow keeps everything in one terminal and gives you full control! 🚀

