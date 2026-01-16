# Logging and Monitoring Guide

## Overview

Dilla AI now has comprehensive logging and monitoring capabilities to help debug issues and get to production.

## Log Files

All log files are stored in the `./logs/` directory:

- **`backend.log`** - All backend application logs (INFO level and above)
- **`backend_errors.log`** - Error-level logs only (ERROR, CRITICAL)
- **`frontend.log`** - Frontend Next.js logs

### Log Rotation

- Logs automatically rotate when they reach 10MB
- Backend logs keep 5 backups
- Error logs keep 10 backups (to preserve more error history)

## Monitoring Commands

### Real-time Monitoring

```bash
# Monitor all logs simultaneously
./monitor_logs.sh all

# Monitor only backend logs
./monitor_logs.sh backend

# Monitor only frontend logs
./monitor_logs.sh frontend

# Monitor only errors
./monitor_logs.sh errors

# View log statistics
./monitor_logs.sh stats

# Search logs for specific terms
./monitor_logs.sh search "error"
./monitor_logs.sh search "database"
```

### Manual Log Viewing

```bash
# View recent backend logs
tail -f logs/backend.log

# View recent errors
tail -f logs/backend_errors.log

# View recent frontend logs
tail -f logs/frontend.log

# View last 100 lines of backend log
tail -100 logs/backend.log
```

## Log Format

### Backend Logs

Backend logs include:
- Timestamp
- Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Logger name
- Function name
- Line number
- Message

Example format:
```
2025-01-27 14:30:45 | INFO     | dilla_ai             | lifespan           | Starting up Dilla AI Backend...
```

### Frontend Logs

Frontend logs follow Next.js standard output format.

## Starting Services

```bash
# Start both frontend and backend with logging
./start_services.sh

# Stop services
./stop_services.sh
```

When services start:
- Backend logs automatically go to `logs/backend.log` and `logs/backend_errors.log`
- Frontend logs automatically go to `logs/frontend.log`
- PIDs are saved to `backend.pid` and `frontend.pid` for easy stopping

## Debugging Tips

### 1. Check Service Health

```bash
# Backend health check
curl http://localhost:8000/health

# Frontend (should return HTML)
curl http://localhost:3001
```

### 2. Common Issues

**Backend not starting:**
```bash
# Check backend logs
tail -50 logs/backend.log
tail -50 logs/backend_errors.log
```

**Frontend not starting:**
```bash
# Check frontend logs
tail -50 logs/frontend.log
```

**Port already in use:**
```bash
# Kill processes on ports
lsof -ti:8000 | xargs kill -9
lsof -ti:3001 | xargs kill -9

# Then restart
./start_services.sh
```

### 3. Search for Specific Issues

```bash
# Search for database errors
./monitor_logs.sh search "database"

# Search for API errors
./monitor_logs.sh search "api"

# Search for connection errors
./monitor_logs.sh search "connection"
```

### 4. Monitor Real-time Activity

Open multiple terminal windows:
- Terminal 1: `./monitor_logs.sh errors` (for critical issues)
- Terminal 2: `./monitor_logs.sh backend` (for backend activity)
- Terminal 3: `./monitor_logs.sh frontend` (for frontend activity)

## Production Preparation

### Log Levels

Current log level: **INFO**

To change log levels:
- Edit `backend/app/main.py` - change `level="INFO"` to desired level
- Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Structured Logging (JSON)

To enable JSON formatted logs for easier parsing:
- Edit `backend/app/core/logging_config.py`
- Change `enable_json=False` to `enable_json=True` in `backend/app/main.py`

### Log Aggregation

For production, consider:
1. **CloudWatch / Datadog** - Send logs to cloud services
2. **ELK Stack** - Elasticsearch, Logstash, Kibana
3. **Sentry** - Error tracking and monitoring

## Quick Reference

| Action | Command |
|--------|---------|
| Start services | `./start_services.sh` |
| Stop services | `./stop_services.sh` |
| Monitor all logs | `./monitor_logs.sh all` |
| Monitor errors | `./monitor_logs.sh errors` |
| View stats | `./monitor_logs.sh stats` |
| Search logs | `./monitor_logs.sh search <term>` |

## Troubleshooting

If logs aren't appearing:
1. Check that `logs/` directory exists: `mkdir -p logs`
2. Verify services are running: `ps aux | grep uvicorn` or `ps aux | grep "next dev"`
3. Check file permissions: `ls -la logs/`
4. Verify backend has write access to logs directory

