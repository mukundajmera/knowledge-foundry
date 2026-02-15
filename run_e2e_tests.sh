#!/usr/bin/env bash
# run_e2e_tests.sh

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "🚀 RUNNING E2E TEST SUITE"
echo "========================================"

# 1. Infrastructure Tests
echo ""
echo "📦 [1/3] Testing Infrastructure..."
chmod +x tests/e2e/test_infrastructure.sh
./tests/e2e/test_infrastructure.sh

# 2. API Tests
echo ""
echo "🔌 [2/3] Testing API..."
if [[ -d ".venv" ]]; then
    # Add marker to pytest.ini if needed, or just ignore warning
    .venv/bin/pytest tests/e2e/test_api_e2e.py -v -m e2e 2>/dev/null || \
    .venv/bin/pytest tests/e2e/test_api_e2e.py -v
else
    echo "⚠️  No virtual environment found, skipping Python API tests"
fi

# 3. UI Tests (if node_modules exists)
echo ""
echo "🖥️  [3/3] Testing UI check..."
if curl -s -f http://localhost:3000 >/dev/null; then
    echo "✓ UI is reachable at http://localhost:3000"
else
    echo "✗ UI is not reachable"
    exit 1
fi

if [[ -d "frontend/node_modules" ]]; then
    echo "🎭 Running Playwright E2E tests..."
    cd frontend && npx playwright test
    cd ..
else
    echo "⚠️  Skipping Playwright tests (dependencies not installed)"
fi

echo ""
echo "========================================"
echo "✅ E2E SUITE COMPLETED SUCCESSFULLY"
echo "========================================"
