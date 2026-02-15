# User Guide

How to use Knowledge Foundry for AI-powered knowledge management.

## Getting Started

1. **Access the UI**: http://localhost:3000
2. **Or use the API**: http://localhost:8000/docs

## Making Queries

### Simple Query (Web UI)

1. Enter your question in the text box
2. Click "Submit"
3. View the response with sources

### Advanced Query (Multi-Agent)

Enable "Use Supervisor" to:
- Deep research with web search
- Multi-step reasoning
- Quality review
- Code generation

### Using Specific Providers

Choose from:
- **Anthropic** (default) - Cloud, high quality
- **Oracle Code Assist** - Cloud, code-focused
- **LM Studio** - Local, free
- **Ollama** - Local, free

## Document Management

### Upload Documents

1. Click "Upload Document"
2. Select PDF, TXT, MD, or DOCX
3. Wait for indexing (automatic)
4. Documents are now searchable

### Search Documents

Your queries automatically search uploaded documents using:
- Vector similarity (semantic search)
- Knowledge graph (relationship discovery)

## Query Types

### Question Answering
```
"What is the capital of France?"
"Explain quantum computing in simple terms"
```

### Summarization
```
"Summarize the uploaded research paper"
"What are the key points from the meeting notes?"
```

### Code Generation
```
"Write a Python function to sort a list"
"Create a React component for a login form"
```
(Uses Code Sandbox for safe execution)

### Research
```
"Research the latest AI trends and summarize findings"
"Compare different database technologies"
```
(Uses multi-agent with web search)

### Analysis
```
"Analyze this data and provide insights: [data]"
"What are the implications of this policy change?"
```

## Understanding Responses

### Model Tier Indicators

- **🔷 Haiku**: Fast, simple queries
- **🟢 Sonnet**: Standard queries, code
- **🔴 Opus**: Complex reasoning, architecture

### Cost Tracking

Each response shows:
- Token usage (input + output)
- Estimated cost in USD
- Model used

### Source Citations

Responses include sources when:
- Using RAG (document retrieval)
- Web search enabled
- Knowledge graph traversal

## Advanced Features

### Force Specific Model

Use API to force a tier:
```json
{
  "query": "...",
  "force_model": "opus"
}
```

### Adjust Parameters

```json
{
  "query": "...",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

- **temperature**: 0.0 (deterministic) to 1.0 (creative)
- **max_tokens**: Response length limit

### Use Local Models

Switch to local inference (zero cost):
```json
{
  "query": "...",
  "provider": "ollama"
}
```

## Monitoring

### View Metrics

**Grafana**: http://localhost:3001
- Query latency
- Cost tracking
- Error rates
- Cache hit rates

**Langfuse**: Track LLM calls end-to-end

### Check Health

http://localhost:8000/health

Shows status of all services.

## Best Practices

1. **Be Specific**: Detailed questions get better answers
2. **Provide Context**: Include relevant background info
3. **Use Supervisor for Complex Tasks**: Research, multi-step reasoning
4. **Upload Documents**: Better context = better answers
5. **Monitor Costs**: Check token usage for budget control

## Troubleshooting

**Slow responses?**
- Check which model tier is being used
- Consider using local providers (Ollama)

**No results from documents?**
- Verify documents are indexed: http://localhost:8000/api/v1/documents
- Check similarity threshold (may need lowering)

**Rate limited?**
- Authenticate for higher limits
- Wait for rate limit window to reset

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more help.
