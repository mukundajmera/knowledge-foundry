# DevOps Script: kf.sh

## Quick Start

```bash
# Make executable (already done)
chmod +x kf.sh

# Start the entire stack
./kf.sh start

# Check status
./kf.sh status

# View logs
./kf.sh logs

# Stop everything
./kf.sh stop
```

## All Commands

| Command | Description |
|---------|-------------|
| `./kf.sh start` | Start entire stack with health checks |
| `./kf.sh stop` | Stop all services |
| `./kf.sh restart` | Restart all services |
| `./kf.sh status` | Show health status of all services |
| `./kf.sh logs [service]` | Stream logs (all or specific service) |
| `./kf.sh clean` | Remove containers + volumes (⚠ destroys data) |
| `./kf.sh rebuild` | Rebuild Docker images |
| `./kf.sh test` | Run pytest suite |
| `./kf.sh shell [service]` | Open shell in container |
| `./kf.sh db-migrate` | Run Alembic migrations |
| `./kf.sh help` | Show help |

## Startup Sequence

The `start` command uses a phased approach with health checks:

1. **Infrastructure** (Qdrant, Redis, PostgreSQL, Neo4j)
2. **Application** (FastAPI backend)
3. **Frontend** (Next.js)
4. **Monitoring** (Prometheus, Grafana)

Each phase waits for health checks before proceeding.

## Service URLs

After `./kf.sh start`, access:

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/kf_admin)
- **Prometheus**: http://localhost:9090
- **Neo4j**: http://localhost:7474 (neo4j/kf_dev_password)

## Examples

```bash
# Start and monitor
./kf.sh start && ./kf.sh logs api

# View specific service logs
./kf.sh logs postgres

# Connect to database
./kf.sh shell postgres
# Inside container: psql -U kf_user -d knowledge_foundry

# Run migrations
./kf.sh db-migrate

# Full cleanup and restart
./kf.sh clean && ./kf.sh start
```

## Verification

Run the test script:

```bash
./test_kf.sh
```

All 13 tests should pass.
