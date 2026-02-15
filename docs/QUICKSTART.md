# Quick Start Guide

Get Knowledge Foundry running in 5 minutes.

## Prerequisites

- **Docker Desktop** (for Mac/Windows) or **Docker Engine** (for Linux)
- **Python 3.12+**
- **Git**
- **API Keys**:
  - Anthropic API key (required)
  - OpenAI API key (optional, for embeddings)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/knowledge-foundry.git
cd knowledge-foundry

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Step 2: Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your preferred editor
```

**Minimum required configuration:**
```bash
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here  # For embeddings
```

## Step 3: Start the Stack

```bash
# Start all services (infrastructure + application + frontend + monitoring)
./kf.sh start
```

This will:
1. Start infrastructure (Qdrant, Redis, PostgreSQL, Neo4j)
2. Wait for health checks
3. Start the API backend
4. Start the frontend
5. Start monitoring (Prometheus, Grafana)

**Expected output:**
```
✓ Qdrant is healthy
✓ Redis is healthy  
✓ PostgreSQL is healthy
✓ Neo4j is healthy
✓ API is healthy
✓ Frontend is healthy
✓ Knowledge Foundry is running!

📊 Service URLs:
   Frontend:    http://localhost:3000
   API:         http://localhost:8000
   API Docs:    http://localhost:8000/docs
   Grafana:     http://localhost:3001 (admin/kf_admin)
   ...
```

## Step 4: Verify

Open your browser:

### Frontend
http://localhost:3000

### API Documentation
http://localhost:8000/docs

Try the `/health` endpoint to verify everything is running.

### Grafana Dashboard
http://localhost:3001
- Username: `admin`
- Password: `kf_admin`

## Step 5: Make Your First Request

### Via Web UI
1. Open http://localhost:3000
2. Enter a query like "Explain quantum computing"
3. Click Submit

### Via curl
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RAG?",
    "use_supervisor": true
  }'
```

### Via Python
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/query",
    json={
        "query": "Explain the Knowledge Foundry architecture",
        "use_supervisor": True
    }
)
print(response.json())
```

## Common Commands

```bash
# Check status
./kf.sh status

# View logs
./kf.sh logs          # All services
./kf.sh logs api      # Just API
./kf.sh logs frontend # Just frontend

# Stop all services
./kf.sh stop

# Restart
./kf.sh restart

# Run tests
./kf.sh test

# Clean everything (⚠ destroys data)
./kf.sh clean
```

## Next Steps

- 📖 Read the [User Guide](USER_GUIDE.md)
- 🔧 Review [Configuration Options](CONFIGURATION.md)
- 🏗️ Understand the [Architecture](ARCHITECTURE_OVERVIEW.md)
- 🛠️ Start [Developing](DEVELOPER_GUIDE.md)

## Troubleshooting

### Docker not running
```
✗ Docker daemon is not running. Please start Docker Desktop.
```
**Solution**: Start Docker Desktop

### Port already in use
```
Error: bind: address already in use
```
**Solution**: Stop the service using the port or change the port in `docker-compose.yml`

### Health check timeout
**Solution**: Wait longer or check logs: `./kf.sh logs <service>`

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.
