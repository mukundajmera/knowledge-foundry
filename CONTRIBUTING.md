# Contributing to Knowledge Foundry

Thank you for considering contributing! This guide will help you get started.

## Code of Conduct

Be respectful, inclusive, and collaborative.

## Quick Start

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/knowledge-foundry.git
cd knowledge-foundry

# Setup development environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start infrastructure
./kf.sh start

# Run tests
pytest tests/ -v
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 2. Make Changes

```bash
# Make your changes
# Add tests
# Update documentation
```

### 3. Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests with coverage
pytest tests/ --cov=src --cov-report=html

# Lint
ruff check src/
black --check src/

# Type check
mypy src/
```

### 4. Commit

```bash
# Use conventional commits
git commit -m "feat: add new LLM provider"
git commit -m "fix: resolve circuit breaker issue"
git commit -m "docs: update API documentation"
```

**Commit Prefixes:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `test:` Adding/updating tests
- `refactor:` Code refactoring
- `perf:` Performance improvement
- `chore:` Maintenance

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## PR Guidelines

### PR Title
Use conventional commits format:
```
feat: add Gemini LLM provider
fix: resolve RAG reranking bug
```

### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Changelog updated
```

## Code Style

### Python
```python
# Use Black formatting
black src/

# Use Ruff for linting
ruff check src/ --fix

# Type hints required
def process_query(query: str, config: LLMConfig) -> LLMResponse:
    ...

# Docstrings for public APIs
def generate(self, prompt: str) -> str:
    \"\"\"Generate a response from the LLM.
    
    Args:
        prompt: The input prompt.
        
    Returns:
        The generated text.
        
    Raises:
        LLMProviderError: If the API call fails.
    \"\"\"
```

### TypeScript (Frontend)
```typescript
// Use ESLint + Prettier
npm run lint
npm run format

// Use TypeScript strict mode
// Add types for all functions
export async function fetchData(id: string): Promise<Data> {
  // ...
}
```

## Testing Guidelines

### Unit Tests
```python
# tests/unit/test_feature.py
import pytest
from src.module import Feature

class TestFeature:
    @pytest.fixture
    def feature(self):
        return Feature()
    
    def test_basic_functionality(self, feature):
        result = feature.process("input")
        assert result == "expected"
    
    def test_error_handling(self, feature):
        with pytest.raises(ValueError):
            feature.process(None)
```

### Integration Tests
```python
# tests/integration/test_flow.py
@pytest.mark.asyncio
async def test_end_to_end_flow():
    response = await client.post("/api/v1/query", json={"query": "test"})
    assert response.status_code == 200
    assert "text" in response.json()
```

### Test Coverage
Aim for > 90% coverage. Check with:
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Adding a New LLM Provider

1. **Implement Provider**
```python
# src/llm/providers.py
class NewProvider(LLMProvider):
    async def generate(self, prompt: str, config: LLMConfig) -> LLMResponse:
        # Implementation
        pass
    
    async def health_check(self) -> bool:
        pass
    
    def get_cost_per_token(self, model: str) -> tuple[float, float]:
        pass
```

2. **Add Configuration**
```python
# src/core/config.py
class NewProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEWPROVIDER_")
    api_key: str = Field(default="")
    model: str = Field(default="default-model")
```

3. **Register in DI Container**
```python
# src/core/dependencies.py
if settings.newprovider.api_key:
    provider = NewProvider(settings=settings.newprovider)
    container.llm_router.register_provider("newprovider", provider)
```

4. **Add Tests**
```python
# tests/unit/test_providers.py
class TestNewProvider:
    def test_generate_success(self):
        # ...
```

5. **Update Documentation**
- Add to README.md
- Add to CONFIGURATION.md
- Add env vars to .env.example

## Adding a New Agent

1. **Implement Agent**
```python
# src/agents/agents.py
class NewAgent(Agent):
    async def execute(self, task: AgentTask) -> AgentResult:
        # Implementation
        pass
```

2. **Register in Supervisor**
```python
# src/agents/supervisor.py
self._specialized_agents["new_task_type"] = NewAgent(...)
```

3. **Add Tests**

4. **Update Documentation**

## Documentation

- Update `/docs` for significant changes
- Use clear, concise language
- Include code examples
- Add Mermaid diagrams for architecture changes

## Release Process

Maintainers will:
1. Review PR
2. Run CI/CD tests
3. Merge to main
4. Tag release
5. Update CHANGELOG.md

## Questions?

- Open an issue: https://github.com/your-org/knowledge-foundry/issues
- Discussions: https://github.com/your-org/knowledge-foundry/discussions

Thank you for contributing! 🙏
