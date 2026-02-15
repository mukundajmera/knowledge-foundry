#!/usr/bin/env bash
# tests/e2e/test_infrastructure.sh

set -e

echo "🧪 E2E Test: Infrastructure Deployment"

# 1. Start infrastructure if not running
echo "🚀 Checking infrastructure..."
./kf.sh start

# 2. Verify each service
echo "✅ Verifying services..."

# Qdrant
if curl -s -f http://localhost:6333/healthz >/dev/null 2>&1; then
    echo "✓ Qdrant is healthy"
else
    echo "✗ Qdrant failed"
    exit 1
fi

# Redis
if nc -z localhost 6379 2>/dev/null; then
    echo "✓ Redis is healthy"
else
    echo "✗ Redis failed"
    exit 1
fi

# PostgreSQL
if nc -z localhost 5432 2>/dev/null; then
    echo "✓ PostgreSQL is healthy"
else
    echo "✗ PostgreSQL failed"
    exit 1
fi

# Neo4j
if curl -s -f http://localhost:7474 >/dev/null 2>&1; then
    echo "✓ Neo4j is healthy"
else
    echo "✗ Neo4j failed"
    exit 1
fi

# API
if curl -s -f http://localhost:8000/health >/dev/null 2>&1; then
    echo "✓ API is healthy"
else
    echo "✗ API failed"
    exit 1
fi

# Frontend
if curl -s -f http://localhost:3000 >/dev/null 2>&1; then
    echo "✓ Frontend is healthy"
else
    echo "✗ Frontend failed"
    exit 1
fi

echo ""
echo "✅ All infrastructure tests passed!"
