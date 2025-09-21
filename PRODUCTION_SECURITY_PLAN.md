# Production Security & Reliability Plan

## Status: API Keys are SECURE ✅
- All `.env` files are properly gitignored
- No API keys found in commit history
- Only example files with placeholders are tracked

## 1. Multi-LLM Fallback System

### Primary Goal
Ensure 99.9% uptime by implementing intelligent fallback between LLM providers.

### Provider Hierarchy
1. **Primary**: Claude 3.5 Sonnet (best quality)
2. **Secondary**: Gemini 1.5 Pro (10x cheaper, good quality)
3. **Tertiary**: GPT-4 Turbo (fallback option)

### Implementation Plan

#### Phase 1: LLM Abstraction Layer
```python
backend/app/services/llm/
├── __init__.py
├── llm_provider.py       # Abstract base class
├── providers/
│   ├── claude_provider.py
│   ├── gemini_provider.py
│   └── openai_provider.py
├── llm_manager.py         # Orchestration & fallback logic
├── cost_tracker.py        # Track and optimize costs
└── prompt_adapter.py      # Provider-specific prompt optimization
```

#### Phase 2: Intelligent Routing
- **Circuit Breaker**: Automatically disable failing providers for 5 minutes
- **Performance Tracking**: Route to fastest provider based on rolling averages
- **Cost Optimization**: Route simple queries to cheaper providers
- **Quality Tiers**: High/Medium/Low quality requirements

### Cost Comparison (per 1M tokens)
| Provider | Input Cost | Output Cost | Speed | Quality |
|----------|------------|-------------|-------|---------|
| Claude 3.5 | $3.00 | $15.00 | Fast | Excellent |
| Gemini 1.5 | $0.25 | $0.50 | Fast | Good |
| GPT-4 Turbo | $10.00 | $30.00 | Medium | Excellent |

## 2. API Key Security

### Development Environment
```bash
# .env (local only, never committed)
CLAUDE_API_KEY=sk-ant-api03-xxx
GEMINI_API_KEY=AIzaSyxxx
OPENAI_API_KEY=sk-proj-xxx
```

### Staging Environment
Use encrypted environment variables:
```python
# Encrypted with master key from AWS KMS
CLAUDE_API_KEY_ENCRYPTED=gAAAAABh...
GEMINI_API_KEY_ENCRYPTED=gAAAAABh...
```

### Production Environment
**AWS Secrets Manager** (Recommended)
```python
# Secrets stored in AWS, never in code
aws secretsmanager create-secret \
  --name prod/llm/api_keys \
  --secret-string '{"claude":"sk-ant-xxx","gemini":"AIza-xxx"}'
```

**Alternative: HashiCorp Vault**
```bash
vault kv put secret/api_keys \
  claude=sk-ant-xxx \
  gemini=AIza-xxx
```

## 3. Security Implementation Checklist

### Immediate Actions (Day 1)
- [ ] Set up LLM fallback system
- [ ] Implement prompt sanitization
- [ ] Add rate limiting (100/hour per IP)
- [ ] Enable request signing validation
- [ ] Set up basic monitoring

### Pre-Production (Day 2-3)
- [ ] Configure AWS Secrets Manager
- [ ] Implement circuit breakers
- [ ] Add comprehensive logging
- [ ] Set up cost tracking
- [ ] Enable bot detection

### Production Deployment (Day 4-5)
- [ ] Deploy with encrypted secrets
- [ ] Configure CloudFlare WAF
- [ ] Enable DDoS protection
- [ ] Set up alerts for failures
- [ ] Implement key rotation

## 4. Prompt Injection Protection

### Input Sanitization
```python
class PromptSecurity:
    forbidden_patterns = [
        "ignore previous instructions",
        "reveal system prompt",
        "</system>",
        "admin override"
    ]
    
    def validate(self, prompt: str) -> str:
        # Check for injection attempts
        # Escape special characters
        # Wrap in safety tags
        return sanitized_prompt
```

### Company Name Validation
- Only alphanumeric + basic punctuation
- Maximum length: 100 characters
- No special characters or code

## 5. Anti-Scraping & Rate Limiting

### Rate Limits by Tier
| User Type | Requests/Hour | Requests/Day | Concurrent |
|-----------|---------------|--------------|------------|
| Free | 20 | 100 | 1 |
| Pro | 100 | 1000 | 3 |
| Enterprise | 1000 | 10000 | 10 |

### Bot Detection Signals
- Request frequency < 500ms between
- No JavaScript execution
- Suspicious user agents
- Sequential pattern detection
- Direct API access without frontend

## 6. Monitoring & Alerts

### Key Metrics to Track
- LLM provider uptime
- Average response time
- Cost per request
- Error rates by provider
- Security incidents

### Alert Thresholds
- Claude failure rate > 10%
- Response time > 10s
- Cost spike > 2x normal
- Suspected bot activity
- API key usage anomaly

## 7. Pre-Commit Security Hooks

### Setup Instructions
```bash
# Install pre-commit
pip install pre-commit detect-secrets

# Create configuration
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
EOF

# Install hooks
pre-commit install

# Create baseline
detect-secrets scan > .secrets.baseline
```

## 8. Emergency Response Plan

### If API Key is Exposed
1. **Immediate**: Rotate the key
2. **Within 5 min**: Deploy new key to production
3. **Within 1 hour**: Audit logs for unauthorized usage
4. **Within 24 hours**: Post-mortem analysis

### If Provider Goes Down
1. Automatic failover to next provider
2. Alert team via Slack/PagerDuty
3. Monitor cost implications
4. Consider temporary rate limiting

## 9. Cost Optimization Strategy

### Routing Logic
```python
if complexity == "simple":
    use_provider("gemini")  # 10x cheaper
elif complexity == "medium":
    use_provider("gemini")  # Still good enough
elif complexity == "complex":
    use_provider("claude")  # Best quality
```

### Expected Monthly Costs
- Development: ~$50
- Staging: ~$200
- Production (1K users): ~$2,000
- Production (10K users): ~$15,000

## 10. Implementation Timeline

### Week 1 (Before Production)
- **Monday**: Implement LLM fallback system
- **Tuesday**: Add security measures
- **Wednesday**: Set up monitoring
- **Thursday**: Load testing
- **Friday**: Deploy to production

### Post-Launch
- Week 2: Monitor and optimize
- Week 3: Implement cost optimizations
- Month 2: Add advanced features

## Testing Commands

### Test Fallback System
```bash
# Simulate Claude failure
export SIMULATE_CLAUDE_FAILURE=true
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -d '{"prompt": "Test fallback to Gemini"}'
```

### Test Rate Limiting
```bash
# Should fail after 20 requests
for i in {1..25}; do
  curl -X POST http://localhost:8000/api/agent/unified-brain \
    -d '{"prompt": "Test rate limit"}'
done
```

### Security Scan
```bash
# Run security check
python scripts/security_check.py

# Check for exposed secrets
detect-secrets scan --all-files
```

## Deployment Checklist

### Before Going Live
- [ ] All API keys in secure storage
- [ ] LLM fallback tested
- [ ] Rate limiting active
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] Cost tracking enabled
- [ ] Security scan passed
- [ ] Load testing completed
- [ ] Backup provider tested
- [ ] Emergency contacts updated

---

**Last Updated**: 2025-09-20
**Status**: Ready for Implementation
**Priority**: CRITICAL - Must complete before production