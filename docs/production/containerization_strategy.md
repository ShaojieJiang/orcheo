# Containerization Strategy for Orcheo

## Executive Summary

**Yes, containerizing Orcheo services is strongly recommended** for production deployments. This document outlines the strategic benefits and provides a comprehensive implementation plan.

## Why Containerize?

### 1. Ease of Deployment

**Current Pain Points:**
- Manual dependency installation (`uv sync`, npm install)
- Python 3.12+ requirement with version management
- Node.js environment setup for Canvas
- Platform-specific binary dependencies (e.g., `py-mini-racer`, `selenium`)
- Environment variable configuration complexity
- Multiple service coordination (backend, Canvas, database)

**Container Benefits:**
- Single `docker compose up` command for full stack
- Consistent runtime across development, staging, and production
- Pre-built images eliminate build time on deployment
- Automatic dependency resolution and caching
- Version-locked deployments (no "works on my machine")

### 2. Security

**Current Risks:**
- Direct host filesystem access (`~/.orcheo/`, SQLite databases)
- Shared Python environment with system packages
- Unrestricted network access from workflow execution
- Credential storage on host filesystem
- No resource limits on workflow execution

**Container Security Benefits:**
- **Isolation**: Separate containers for backend, Canvas, and databases
- **Read-only filesystems**: Prevent runtime modification
- **Network segmentation**: Internal Docker networks for service-to-service communication
- **Resource limits**: CPU/memory caps prevent DoS via malicious workflows
- **Secrets management**: Docker secrets or Kubernetes secrets instead of `.env` files
- **Minimal attack surface**: Alpine-based images with only required dependencies
- **Non-root execution**: Run services as unprivileged users
- **Image scanning**: Automated vulnerability detection in CI/CD

### 3. Additional Benefits

- **Scalability**: Horizontal scaling with container orchestration (Kubernetes, Docker Swarm)
- **Observability**: Centralized logging and monitoring via container platforms
- **Disaster Recovery**: Image registry serves as deployment artifact backup
- **Multi-tenancy**: Isolated environments per customer/team
- **Development Parity**: Identical environments for all developers

## Current State Assessment

### Existing Containerization
- ✅ DevContainer for VS Code (`.devcontainer/Dockerfile`)
- ❌ No production Dockerfile
- ❌ No Docker Compose configuration
- ❌ No multi-stage build optimization
- ❌ No image publishing pipeline

### Architecture Components
1. **Backend Service** (`apps/backend/src/orcheo_backend/`)
   - FastAPI application
   - Python 3.12+, `uv` dependency management
   - Multiple backends: SQLite (dev), PostgreSQL (prod)
2. **Canvas Service** (`apps/canvas/`)
   - React + Vite application
   - Node.js-based build and preview
3. **Database Services**
   - SQLite (local development)
   - PostgreSQL (production)
4. **Supporting Services**
   - External integrations: Telegram Bot, Slack, MongoDB, RSS feeds

## Implementation Roadmap

### Phase 1: Core Containerization (Week 1-2)

#### 1.1 Backend Production Dockerfile

**Location:** `/Dockerfile.backend`

**Key Requirements:**
- Multi-stage build (builder + runtime)
- Alpine Linux base for minimal footprint
- `uv` for dependency installation
- Non-root user execution
- Health check endpoint
- Configurable via environment variables

**Example Structure:**
```dockerfile
# Stage 1: Builder
FROM python:3.12-alpine AS builder
RUN apk add --no-cache curl gcc musl-dev
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY apps/backend apps/backend
COPY packages packages
COPY src src
RUN /root/.local/bin/uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-alpine
RUN apk add --no-cache libgcc libstdc++
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build /app
WORKDIR /app
RUN adduser -D -u 1000 orcheo
USER orcheo
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8000/docs || exit 1
CMD ["/app/.venv/bin/uvicorn", "orcheo_backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Security Hardening:**
- Read-only root filesystem with writable `/tmp` mount
- Drop all capabilities except `CAP_NET_BIND_SERVICE`
- No privileged mode
- Security scanning in CI (Trivy, Grype)

#### 1.2 Canvas Production Dockerfile

**Location:** `/Dockerfile.canvas`

**Key Requirements:**
- Multi-stage build (build + nginx serve)
- Node.js LTS for build stage
- Nginx Alpine for serving static assets
- Environment variable injection at runtime

**Example Structure:**
```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /build
COPY apps/canvas/package*.json ./
RUN npm ci --production=false
COPY apps/canvas ./
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY apps/canvas/nginx.conf /etc/nginx/nginx.conf
RUN adduser -D -u 1000 orcheo && \
    chown -R orcheo:orcheo /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

#### 1.3 Docker Compose Development Configuration

**Location:** `/docker-compose.dev.yml`

**Services:**
- `orcheo-backend`: FastAPI application
- `orcheo-canvas`: Canvas UI
- `postgres`: PostgreSQL database
- `pgadmin`: Database management UI (optional)

**Features:**
- Volume mounts for hot-reload during development
- Network isolation (internal network for DB access)
- Named volumes for data persistence
- Environment file loading (`.env`)
- Service dependencies and health checks

**Example:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orcheo
      POSTGRES_USER: orcheo
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-orcheo-dev}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - orcheo-internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orcheo"]
      interval: 10s
      timeout: 5s
      retries: 5

  orcheo-backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      ORCHEO_CHECKPOINT_BACKEND: postgres
      ORCHEO_POSTGRES_DSN: postgresql://orcheo:${POSTGRES_PASSWORD:-orcheo-dev}@postgres:5432/orcheo
      ORCHEO_REPOSITORY_BACKEND: postgres
      ORCHEO_VAULT_BACKEND: file
      ORCHEO_VAULT_ENCRYPTION_KEY: ${VAULT_ENCRYPTION_KEY}
    volumes:
      - ./src:/app/src:ro
      - ./apps/backend:/app/apps/backend:ro
      - vault-data:/app/vault
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - orcheo-internal
      - orcheo-external
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 3s
      retries: 3

  orcheo-canvas:
    build:
      context: .
      dockerfile: Dockerfile.canvas
    ports:
      - "5173:80"
    environment:
      VITE_API_URL: http://localhost:8000
    depends_on:
      - orcheo-backend
    networks:
      - orcheo-external

networks:
  orcheo-internal:
    internal: true
  orcheo-external:

volumes:
  postgres-data:
  vault-data:
```

### Phase 2: Production Hardening (Week 3-4)

#### 2.1 Production Docker Compose

**Location:** `/docker-compose.prod.yml`

**Key Differences from Dev:**
- No volume mounts (immutable deployments)
- Secrets via Docker secrets or external secret manager
- Resource limits (CPU, memory)
- Restart policies (`restart: always`)
- Logging configuration
- Reverse proxy (Nginx/Traefik) with TLS termination

**Example Resource Limits:**
```yaml
services:
  orcheo-backend:
    # ... other config ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
      restart_policy:
        condition: on-failure
        max_attempts: 3
```

#### 2.2 Security Enhancements

**Secrets Management:**
```yaml
services:
  orcheo-backend:
    secrets:
      - postgres_password
      - vault_encryption_key
      - openai_api_key
    environment:
      ORCHEO_POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      ORCHEO_VAULT_ENCRYPTION_KEY_FILE: /run/secrets/vault_encryption_key

secrets:
  postgres_password:
    external: true
  vault_encryption_key:
    external: true
```

**Network Policies:**
- Backend can access: Postgres, external APIs
- Canvas can access: Backend only
- Postgres can access: None (internal only)

**Read-Only Filesystem:**
```yaml
services:
  orcheo-backend:
    read_only: true
    tmpfs:
      - /tmp
      - /app/.cache
```

#### 2.3 Image Publishing Pipeline

**Registry Options:**
- Docker Hub: `orcheo/backend:0.13.1`
- GitHub Container Registry: `ghcr.io/ai-colleagues/orcheo-backend:0.13.1`
- AWS ECR, Google GCR, Azure ACR for private registries

**CI/CD Integration (GitHub Actions):**
```yaml
name: Build and Push Container Images

on:
  push:
    tags:
      - 'v*'

jobs:
  build-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/setup-buildx-action@v2
      - uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v4
        with:
          context: .
          file: Dockerfile.backend
          push: true
          tags: |
            ghcr.io/ai-colleagues/orcheo-backend:${{ github.ref_name }}
            ghcr.io/ai-colleagues/orcheo-backend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Phase 3: Orchestration & Scaling (Week 5-6)

#### 3.1 Kubernetes Manifests

**Location:** `/deploy/k8s/`

**Components:**
- Namespace: `orcheo-prod`
- Deployments: backend, canvas
- StatefulSet: PostgreSQL (or use managed RDS/CloudSQL)
- Services: ClusterIP for internal, LoadBalancer for external
- Ingress: TLS termination, path-based routing
- ConfigMaps: Non-sensitive configuration
- Secrets: Database credentials, API keys
- PersistentVolumeClaims: Database storage

**Example Backend Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orcheo-backend
  namespace: orcheo-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orcheo-backend
  template:
    metadata:
      labels:
        app: orcheo-backend
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: backend
        image: ghcr.io/ai-colleagues/orcheo-backend:0.13.1
        ports:
        - containerPort: 8000
        env:
        - name: ORCHEO_CHECKPOINT_BACKEND
          value: postgres
        - name: ORCHEO_POSTGRES_DSN
          valueFrom:
            secretKeyRef:
              name: orcheo-secrets
              key: postgres-dsn
        resources:
          limits:
            cpu: "2"
            memory: 4Gi
          requests:
            cpu: "1"
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /docs
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /docs
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
```

#### 3.2 Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orcheo-backend-hpa
  namespace: orcheo-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orcheo-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Phase 4: Observability & Monitoring (Week 7-8)

#### 4.1 Logging

**Container Logging:**
- Structured JSON logs to stdout/stderr
- Centralized log aggregation (ELK, Loki, CloudWatch)
- Log retention policies
- PII redaction in logs

**Docker Compose Logging:**
```yaml
services:
  orcheo-backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

#### 4.2 Metrics & Tracing

**Prometheus Integration:**
- FastAPI metrics endpoint (`/metrics`)
- Container metrics via cAdvisor
- Database connection pool metrics

**Tracing:**
- OpenTelemetry integration (already in dependencies)
- Jaeger or Tempo for distributed tracing
- Workflow execution spans

#### 4.3 Health Monitoring

**Healthcheck Endpoints:**
- `/health/live`: Liveness probe (is the app running?)
- `/health/ready`: Readiness probe (can it serve traffic?)
- `/health/startup`: Startup probe (is initialization complete?)

**Monitoring Stack:**
- Prometheus + Grafana for metrics
- AlertManager for incident notifications
- Uptime monitoring (UptimeRobot, Pingdom)

## Migration Path

### For Existing Deployments

**Option 1: Blue-Green Deployment**
1. Deploy containerized stack in parallel to existing
2. Route 10% traffic to containerized version
3. Gradually increase traffic while monitoring
4. Full cutover once validated
5. Decommission old deployment

**Option 2: Database Migration First**
1. Migrate SQLite to PostgreSQL (see `docs/production/postgresql_migration_plan.md`)
2. Update existing deployment to use PostgreSQL
3. Switch to containers with minimal downtime

**Option 3: Fresh Start**
- Suitable for dev/staging environments
- Export workflows via CLI (`orcheo workflow download`)
- Deploy containerized stack
- Re-import workflows (`orcheo workflow upload`)

### Rollback Strategy

**Container Rollback:**
```bash
# Docker Compose
docker compose down
docker compose up --build --force-recreate

# Kubernetes
kubectl rollout undo deployment/orcheo-backend -n orcheo-prod
kubectl rollout status deployment/orcheo-backend -n orcheo-prod
```

**Data Rollback:**
- Database backups before migration
- Snapshot volumes before major changes
- Keep previous container images tagged

## Best Practices

### 1. Image Management
- **Tagging**: Use semantic versioning (`1.2.3`), never rely on `latest` in production
- **Scanning**: Run `docker scan` or Trivy in CI/CD
- **Size**: Optimize layers, use `.dockerignore`, multi-stage builds
- **Registry**: Use private registries for proprietary code

### 2. Environment Configuration
- **12-Factor App**: All config via environment variables
- **Secrets**: Never bake secrets into images
- **Defaults**: Provide sensible defaults for development
- **Validation**: Fail fast if required env vars missing

### 3. Data Persistence
- **Volumes**: Use named volumes, not bind mounts in production
- **Backups**: Automate database backups (daily snapshots)
- **Encryption**: Encrypt volumes at rest (LUKS, cloud provider KMS)

### 4. Networking
- **Principle of Least Privilege**: Only expose necessary ports
- **Internal Networks**: Isolate database from internet
- **Service Discovery**: Use DNS names, not hardcoded IPs
- **TLS**: Terminate TLS at reverse proxy, use internal TLS for sensitive data

### 5. Resource Management
- **Limits**: Always set CPU/memory limits
- **Reservations**: Ensure minimum resources available
- **Quotas**: Namespace-level quotas in Kubernetes
- **Monitoring**: Alert on resource saturation

## Cost Considerations

### Container Hosting Options

| Platform | Pros | Cons | Est. Monthly Cost |
|----------|------|------|-------------------|
| **Docker Compose (VPS)** | Simple, full control | Manual scaling, maintenance | $20-100 (DigitalOcean, Linode) |
| **AWS ECS Fargate** | Serverless, auto-scaling | Vendor lock-in, learning curve | $50-300 (depends on usage) |
| **Google Cloud Run** | Auto-scale to zero, pay-per-use | Stateless only, cold starts | $10-200 (light workloads) |
| **Azure Container Instances** | Simple, fast startup | No orchestration, limited features | $30-200 |
| **Kubernetes (AKS/EKS/GKE)** | Enterprise-grade, portable | Complex, expensive | $200-1000+ (managed clusters) |
| **Fly.io** | Edge deployment, simple CLI | Young platform, fewer regions | $25-150 |
| **Railway** | Developer-friendly, Git-based | Limited customization | $5-100 |

**Recommendation for Small Teams:** Start with Docker Compose on a VPS ($50/month for 4 vCPU, 8GB RAM) or Railway ($20-30/month). Migrate to Kubernetes when scaling beyond 3-5 replicas.

## Security Checklist

- [ ] Run containers as non-root user
- [ ] Enable read-only root filesystem
- [ ] Drop all capabilities, add only required ones
- [ ] Scan images for vulnerabilities (Trivy, Grype, Snyk)
- [ ] Use secrets management (Docker secrets, Kubernetes secrets, Vault)
- [ ] Enable AppArmor/SELinux profiles
- [ ] Set resource limits (CPU, memory, PIDs)
- [ ] Use private registries for proprietary images
- [ ] Implement network policies (Kubernetes)
- [ ] Enable TLS for all external communication
- [ ] Rotate secrets regularly
- [ ] Monitor container escape attempts
- [ ] Audit logs for security events
- [ ] Keep base images updated (automated Dependabot)

## Testing Strategy

### 1. Local Testing
```bash
# Build images
docker compose -f docker-compose.dev.yml build

# Start services
docker compose -f docker-compose.dev.yml up -d

# Run tests inside container
docker compose exec orcheo-backend uv run pytest

# Check logs
docker compose logs -f orcheo-backend

# Cleanup
docker compose down -v
```

### 2. Integration Testing
- Test service-to-service communication
- Verify database migrations
- Test secret injection
- Validate health checks
- Load testing with multiple replicas

### 3. Security Testing
```bash
# Scan for vulnerabilities
trivy image orcheo-backend:latest

# Check for misconfigurations
docker scout cves orcheo-backend:latest

# Runtime security
falco (detects abnormal container behavior)
```

## Next Steps

### Immediate (Week 1)
1. Create `Dockerfile.backend` and `Dockerfile.canvas`
2. Write `docker-compose.dev.yml` for local development
3. Update `CLAUDE.md` with container testing commands
4. Test full stack deployment locally

### Short-term (Week 2-4)
1. Create `docker-compose.prod.yml` with hardening
2. Set up CI/CD for image building and pushing
3. Document deployment process in `docs/deployment.md`
4. Migrate one environment (staging) to containers

### Long-term (Month 2-3)
1. Develop Kubernetes manifests
2. Implement auto-scaling policies
3. Set up observability stack (Prometheus, Grafana)
4. Create runbooks for common operational tasks
5. Conduct security audit and penetration testing

## Conclusion

Containerization is a **strong recommendation** for Orcheo due to:
- **Simplified deployments** across all environments
- **Enhanced security** through isolation and least-privilege principles
- **Operational excellence** with standardized tooling
- **Future scalability** with orchestration platforms

The phased approach allows incremental adoption with minimal risk, starting with local Docker Compose and evolving to Kubernetes for enterprise deployments. The initial investment (2-3 weeks) pays dividends in reduced deployment time, improved security posture, and operational reliability.

**Action Required:** Review this strategy with the team and prioritize Phase 1 implementation (Core Containerization) for the next sprint.
