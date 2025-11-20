# Terminal Usage - Problem Solved! ✅

## The Problem

When you run `make run`, the application starts but **blocks your terminal** - you can't run any other commands until you stop it with `Ctrl+C`.

## The Solution

Use **`make run-bg`** to run in background mode!

---

## ✅ Recommended Way: Background Mode

```bash
# 1. Activate conda environment
conda activate py311

# 2. Start in background
make run-bg
```

**Output:**
```
✓ Application started successfully in background (PID: 70631)
  View logs: make app-logs
  Check status: make app-status
  Stop: make stop
```

**🎉 Your terminal is now FREE to use for other commands!**

---

## Common Usage

### Start Application
```bash
make run-bg
```

### Check Status
```bash
make app-status
```

### View Logs
```bash
make app-logs
```
(Press `Ctrl+C` to exit logs)

### Test While Running
```bash
curl http://localhost:8080/health
make test
```

### Stop Application
```bash
make stop
```

### Restart Application
```bash
make restart-app
```

---

## Complete Workflow Example

```bash
# Terminal stays usable the whole time!
conda activate py311
make run-bg
make app-status
curl http://localhost:8080/health
make test
make app-logs  # Ctrl+C to exit
make stop
```

---

## If You Still Want Foreground Mode

Sometimes you want to see logs in real-time in your terminal:

```bash
make run
```

**Note:** This blocks your terminal. Use a second terminal window for other commands, or press `Ctrl+C` to stop.

---

## Quick Reference

| What You Want | Command |
|---------------|---------|
| Start (don't block terminal) | `make run-bg` ⭐ |
| Start (block terminal, see logs) | `make run` |
| Stop | `make stop` |
| Restart | `make restart-app` |
| Check if running | `make app-status` |
| See logs | `make app-logs` |

---

## Troubleshooting

### "Address already in use"
```bash
make stop
make run-bg
```

### "Application failed to start"
```bash
tail logs/app.log
```

### Can't find logs
```bash
ls -la logs/
# If missing, run: mkdir -p logs
```

---

**That's it! Use `make run-bg` and your terminal stays free!** 🚀

