---
trigger: always_on
---

{
  "workspace_name": "Knowledge Foundry AI Factory",
  "ai_provider": "anthropic",
  "primary_model": "claude-opus-4",
  "secondary_model": "claude-sonnet-3.5",
  "tertiary_model": "claude-haiku-3",
  
  "context_settings": {
    "auto_include_files": [
      "core/interfaces.py",
      "config/schemas.yaml",
      "docs/architecture/*.md",
      "docs/ADRs/*.md",
      "docs/research/enterprise-ai-2026.md"
    ],
    "project_structure_aware": true,
    "dependency_graph_tracking": true,
    "git_history_context": true,
    "max_context_tokens": 200000,
    "hybrid_rag_enabled": true,
    "vector_db": "qdrant",
    "graph_db": "neo4j"
  },
  
  "tiered_intelligence": {
    "enabled": true,
    "cost_aware_routing": true,
    "routing_strategy": "complexity_based",
    "models": {
      "strategist": {
        "model": "claude-opus-4",
        "use_cases": ["architecture_design", "complex_reasoning", "multi_hop_queries", "security_analysis"],
        "cost_per_1m_tokens": 15.00
      },
      "workhorse": {
        "model": "claude-sonnet-3.5",
        "use_cases": ["code_generation", "documentation", "standard_queries", "refactoring"],
        "cost_per_1m_tokens": 3.00
      },
      "sprinter": {
        "model": "claude-haiku-3",
        "use_cases": ["classification", "entity_extraction", "formatting", "validation"],
        "cost_per_1m_tokens": 0.25
      }
    }
  },
  
  "code_generation_profiles": {
    "architecture": {
      "model": "claude-opus-4",
      "temperature": 0.3,
      "system_prompt_file": "./prompts/system/architecture.md",
      "reasoning_framework": "tree_of_thought",
      "output_validation": {
        "require_type_hints": true,
        "require_docstrings": true,
        "require_tests": true,
        "check_security_patterns": true,
        "check_eu_ai_act_compliance": true
      }
    },
    "implementation": {
      "model": "claude-sonnet-3.5",
      "temperature": 0.2,
      "system_prompt_file": "./prompts/system/implementation.md",
      "reasoning_framework": "chain_of_thought",
      "auto_formatting": {
        "formatter": "black",
        "line_length": 100,
        "auto_imports": true
      }
    },
    "testing": {
      "model": "claude-sonnet-3.5",
      "temperature": 0.1,
      "system_prompt_file": "./prompts/system/testing.md",
      "evaluation_tools": ["ragas", "deepeval", "confident_ai"],
      "coverage_target": 0.95,
      "quality_gates": {
        "ragas_score": 0.8,
        "context_precision": 0.9,
        "faithfulness": 0.95
      }
    },
    "security": {
      "model": "claude-opus-4",
      "temperature": 0.4,
      "system_prompt_file": "./prompts/system/security.md",
      "red_team_mode": true,
      "owasp_2026_checklist": true,
      "vulnerability_scanners": ["garak", "nemo_guardrails"]
    }
  },
  
  "prompt_library": {
    "architecture": "./prompts/phase0-architecture/*.md",
    "implementation": "./prompts/phase1-implementation/*.md",
    "plugins": "./prompts/phase2-plugins/*.md",
    "security": "./prompts/phase3-security/*.md",
    "optimization": "./prompts/phase4-optimization/*.md",
    "ui": "./prompts/phase5-ui/*.md",
    "research_context": "./docs/research/enterprise-ai-2026.md"
  },
  
  "quality_gates": {
    "pre_commit": {
      "type_check": "mypy --strict",
      "lint": "ruff check",
      "format_check": "black --check",
      "security_scan": "bandit -r && garak --scan",
      "test": "pytest --cov=src --cov-fail-under=90",
      "ragas_evaluation": "pytest tests/evaluation/test_ragas.py"
    },
    "ai_review": {
      "enabled": true,
      "reviewer_model": "claude-sonnet-3.5",
      "review_criteria": [
        "security_vulnerabilities",
        "performance_bottlenecks",
        "type_safety_violations",
        "documentation_completeness",
        "test_coverage_gaps",
        "eu_ai_act_compliance",
        "prompt_injection_vulnerabilities"
      ]
    },
    "production_gate": {
      "ragas_score_min": 0.8,
      "context_precision_min": 0.9,
      "faithfulness_min": 0.95,
      "semantic_drift_threshold": 0.15,
      "p95_latency_max_ms": 500
    }
  },
  
  "observability": {
    "langfuse": {
      "enabled": true,
      "tracing": true,
      "cost_tracking": true
    },
    "arize_phoenix": {
      "enabled": true,
      "semantic_drift_detection": true,
      "alert_threshold": 0.15
    },
    "prometheus": {
      "enabled": true,
      "metrics_port": 9090
    }
  },
  
  "compliance": {
    "eu_ai_act": {
      "enabled": true,
      "high_risk_systems": true,
      "automatic_logging": true,
      "human_oversight_required": true,
      "technical_documentation_auto_gen": true,
      "immutable_audit_logs": true
    }
  }
}