# Testing Guide

Knowledge Foundry testing strategy and execution.

## Test Structure

```
tests/
├── unit/              # Fast, isolated unit tests (549 tests)
├── integration/       # Service integration tests (27 tests)
├── evaluation/        # RAGAS quality evaluation
└── load/              # k6 load/performance tests
```

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Integration Tests
```bash
# Requires running infrastructure
./kf.sh start
pytest tests/integration/ -v
```

### With Coverage
```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term
open htmlcov/index.html
```

### Specific Test
```bash
pytest tests/unit/test_router.py::TestLLMRouter::test_route_basic -v
```

## Writing Tests

###Unit Test Example
```python
# tests/unit/test_module.py
import pytest
from src.module import MyClass

class TestMyClass:
    @pytest.fixture
    def instance(self):
        return MyClass(config={"key": "value"})
    
    def test_basic_functionality(self, instance):
        result = instance.process("input")
        assert result == "expected_output"
    
    @pytest.mark.asyncio
    async def test_async_method(self, instance):
        result = await instance.async_process("input")
        assert isinstance(result, str)
```

### Integration Test Example
```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_query_endpoint(api_client: AsyncClient):
    response = await api_client.post(
        "/api/v1/query",
        json={"query": "test question"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
```

## Test Coverage

**Current:** 95%+ (576 tests passing)

**Target:** > 90%

Critical modules must have > 95%:
- `src/llm/router.py`
- `src/security/`
- `src/agents/supervisor.py`

## Quality Evaluation (RAGAS)

```bash
# Run RAGAS evaluation
pytest tests/evaluation/test_ragas.py -v
```

Metrics:
- **Faithfulness**: > 0.95 (answers grounded in context)
- **Answer Relevancy**: > 0.9 (answers address question)
- **Context Precision**: > 0.9 (retrieved context is relevant)
- **Context Recall**: > 0.8 (all relevant info retrieved)

## Load Testing

```bash
# Install k6
brew install k6  # macOS

# Run load test
k6 run tests/load/api_load_test.js

# Custom duration/users
k6 run --vus 50 --duration 30s tests/load/api_load_test.js
```

**Targets:**
- P95 latency < 2s
- Throughput > 100 req/s
- Error rate < 1%

## CI/CD

GitHub Actions runs on every PR:
- Linting (ruff, black)
- Type checking (mypy)
- Unit tests
- Integration tests (with Docker Compose)
- Coverage report

## Best Practices

1. **Test Naming**: Use descriptive names
2. **Fixtures**: Share common setup
3. **Mocking**: Mock external services (LLM APIs)
4. **Async**: Use `@pytest.mark.asyncio` for async tests
5. **Cleanup**: Use fixtures to ensure cleanup
6. **Fast**: Keep unit tests < 100ms each
