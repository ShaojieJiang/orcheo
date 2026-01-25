# Execution Worker Deployment Guide

This guide covers deploying the Orcheo execution worker with Celery and Redis.

## Environment Variables

### Required

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `REDIS_URL` | Redis connection URL for Celery broker | `redis://localhost:6379/0` | `redis://redis.example.com:6379/0` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `CELERY_CONCURRENCY` | Number of worker processes | `4` |
| `CELERY_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `info` |

### Example Environment File

Create `/etc/orcheo/orcheo.env`:

```bash
# Redis broker configuration
REDIS_URL=redis://localhost:6379/0

# Worker configuration
CELERY_CONCURRENCY=4
CELERY_LOG_LEVEL=info

# Application settings (inherited from existing Orcheo config)
# ORCHEO_AUTH_MODE=jwt
# ORCHEO_DATABASE_URL=sqlite:///./orcheo.db
```

## Local Development

### Option 1: Docker Compose (Recommended for Quick Start)

Start the full stack with a single command:

```bash
# Build and start all services
make docker-up

# View logs
make docker-logs

# Stop all services
make docker-down
```

This starts:
- **Redis** on port 6379
- **Backend API** on port 8000 (with hot reload)
- **Canvas UI** on port 5173 (with hot reload)
- **Celery Worker** for background task execution
- **Celery Beat** for scheduled task dispatching

The source code is mounted as volumes, so changes are reflected immediately.

### Option 2: Native Commands (Faster Iteration)

For faster debugging and development feedback, run services natively:

#### Prerequisites

1. Install Redis:
   ```bash
   # macOS
   brew install redis
   brew services start redis

   # Or use Docker
   make redis
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

#### Running Services

Start all services in separate terminals:

```bash
# Terminal 1: Start Redis (if using Docker)
make redis

# Terminal 2: Start API server
make dev-server

# Terminal 3: Start Celery worker
make worker

# Terminal 4: Start Celery Beat scheduler (for cron triggers)
make celery-beat
```

## Production Deployment

### systemd Setup

1. Copy systemd unit files:
   ```bash
   sudo cp deploy/systemd/*.service /etc/systemd/system/
   ```

2. Create orcheo user and directories:
   ```bash
   sudo useradd -r -s /bin/false orcheo
   sudo mkdir -p /opt/orcheo /etc/orcheo
   sudo chown orcheo:orcheo /opt/orcheo
   ```

3. Deploy application:
   ```bash
   sudo -u orcheo git clone <repo> /opt/orcheo
   cd /opt/orcheo
   sudo -u orcheo uv venv
   sudo -u orcheo uv sync
   ```

4. Configure environment:
   ```bash
   sudo cp /opt/orcheo/deploy/systemd/orcheo.env.example /etc/orcheo/orcheo.env
   sudo chmod 600 /etc/orcheo/orcheo.env
   # Edit /etc/orcheo/orcheo.env with your settings
   ```

5. Enable and start services:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable orcheo-api orcheo-worker orcheo-beat
   sudo systemctl start orcheo-api orcheo-worker orcheo-beat
   ```

### Operational Runbook

#### Starting Services

```bash
sudo systemctl start orcheo-api
sudo systemctl start orcheo-worker
sudo systemctl start orcheo-beat
```

#### Stopping Services

```bash
# Graceful shutdown (recommended)
sudo systemctl stop orcheo-beat      # Stop scheduler first
sudo systemctl stop orcheo-worker    # Worker will finish current tasks
sudo systemctl stop orcheo-api

# Force stop (if graceful fails after timeout)
sudo systemctl kill orcheo-worker
```

#### Checking Status

```bash
# Service status
sudo systemctl status orcheo-api
sudo systemctl status orcheo-worker
sudo systemctl status orcheo-beat

# View logs
sudo journalctl -u orcheo-api -f
sudo journalctl -u orcheo-worker -f
sudo journalctl -u orcheo-beat -f

# Combined logs
sudo journalctl -u 'orcheo-*' -f
```

#### Monitoring Queue Depth

```bash
# Connect to Redis and check queue length
redis-cli LLEN celery
```

#### Restarting Workers

```bash
# Graceful restart (finish current tasks, then restart)
sudo systemctl reload orcheo-worker

# Full restart
sudo systemctl restart orcheo-worker
```

#### Scaling Workers

To run multiple workers, create copies of the systemd unit:

```bash
# Create additional worker units
for i in {2..4}; do
  sudo cp /etc/systemd/system/orcheo-worker.service \
          /etc/systemd/system/orcheo-worker@$i.service
done

# Start additional workers
sudo systemctl start orcheo-worker@{2..4}
```

### Health Checks

#### Redis Health

```bash
redis-cli ping
# Expected: PONG
```

#### Worker Health

Check if workers are consuming tasks:

```bash
# List active workers
celery -A orcheo_backend.worker.celery_app inspect active

# Check worker stats
celery -A orcheo_backend.worker.celery_app inspect stats
```

### Troubleshooting

#### Workers Not Processing Tasks

1. Check Redis connectivity:
   ```bash
   redis-cli ping
   ```

2. Check worker logs:
   ```bash
   sudo journalctl -u orcheo-worker -n 100
   ```

3. Verify REDIS_URL environment variable is set correctly

#### Runs Stuck in Pending State

1. Check if workers are running:
   ```bash
   sudo systemctl status orcheo-worker
   ```

2. Check queue depth:
   ```bash
   redis-cli LLEN celery
   ```

3. If workers crashed mid-execution, runs may be stuck in `running` state.
   Use the CLI to manually retry:
   ```bash
   orcheo workflow run retry <run_id>
   ```

#### High Memory Usage

1. Reduce worker concurrency:
   ```bash
   # Edit /etc/orcheo/orcheo.env
   CELERY_CONCURRENCY=2
   sudo systemctl restart orcheo-worker
   ```

2. Add memory limits to systemd unit:
   ```ini
   [Service]
   MemoryMax=1G
   ```
