# Dilla AI - API Cost Analysis (September 2025)

## API Pricing Reference

### Tavily Search API
| Search Type | Credits | Cost per Search |
|------------|---------|-----------------|
| Basic Search | 1 credit | $0.0075 |
| **Advanced Search** (Used) | 2 credits | **$0.015** |

*Based on Project Plan: $30/month for 4,000 credits*

### Claude Sonnet 4.5 API
| Token Type | Price per 1M Tokens | Price per 1K Tokens |
|------------|---------------------|---------------------|
| Input | $3.00 | $0.003 |
| Output | $15.00 | $0.015 |

### OpenAI GPT-4o API (Fallback)
| Model | Input (per 1M) | Output (per 1M) |
|-------|----------------|-----------------|
| GPT-4o | $5.00 | $15.00 |
| GPT-4o-mini | $0.15 | $0.60 |

---

## System Operation Flow & Costs

### 1. Single Company Query (`@CompanyName`)

#### API Calls Sequence:

| Step | Service | Operation | Details | Est. Cost |
|------|---------|-----------|---------|-----------|
| 1 | Tavily | 4x Advanced Searches | - `{company} startup funding valuation revenue`<br>- `{company} company business model team founders`<br>- `{company} Series A B C funding round investors`<br>- `{company} technology product customers market` | 4 × $0.015 = **$0.060** |
| 2 | Claude Sonnet 4.5 | Extract Company Profile | ~20K input tokens (search results) + ~2K output tokens | (20×$0.003) + (2×$0.015) = **$0.090** |
| 3 | Claude Sonnet 4.5 | Gap Filling & Inference | ~5K input + ~1K output | (5×$0.003) + (1×$0.015) = **$0.030** |
| 4 | Claude Sonnet 4.5 | Valuation Analysis | ~3K input + ~1K output | (3×$0.003) + (1×$0.015) = **$0.024** |
| 5 | Claude Sonnet 4.5 | Format Output | ~2K input + ~2K output | (2×$0.003) + (2×$0.015) = **$0.036** |

**Total Single Company Cost: $0.240**

### 2. Two Company Comparison Query

#### API Calls Sequence:

| Step | Service | Operation | Details | Est. Cost |
|------|---------|-----------|---------|-----------|
| 1 | Tavily | 8x Advanced Searches | 4 searches per company × 2 companies | 8 × $0.015 = **$0.120** |
| 2 | Claude Sonnet 4.5 | Extract 2 Company Profiles | ~40K input + ~4K output | (40×$0.003) + (4×$0.015) = **$0.180** |
| 3 | Claude Sonnet 4.5 | Gap Filling (2x) | ~10K input + ~2K output | (10×$0.003) + (2×$0.015) = **$0.060** |
| 4 | Claude Sonnet 4.5 | Comparison Analysis | ~5K input + ~2K output | (5×$0.003) + (2×$0.015) = **$0.045** |
| 5 | Claude Sonnet 4.5 | Valuation (2x) | ~6K input + ~2K output | (6×$0.003) + (2×$0.015) = **$0.048** |
| 6 | Claude Sonnet 4.5 | Cap Table Generation | ~4K input + ~2K output | (4×$0.003) + (2×$0.015) = **$0.042** |
| 7 | Claude Sonnet 4.5 | Exit Modeling | ~4K input + ~2K output | (4×$0.003) + (2×$0.015) = **$0.042** |
| 8 | Claude Sonnet 4.5 | Deck Generation | ~10K input + ~5K output | (10×$0.003) + (5×$0.015) = **$0.105** |

**Total Two Company Comparison Cost: $0.642**

---

## Cost Matrix by Output Format

| Query Type | Output Format | Tavily Costs | Claude Costs | Total Cost |
|------------|---------------|--------------|--------------|------------|
| **Single Company** | Analysis | $0.060 | $0.180 | **$0.240** |
| **Single Company** | Matrix | $0.060 | $0.200 | **$0.260** |
| **Single Company** | Docs | $0.060 | $0.220 | **$0.280** |
| **Two Companies** | Analysis | $0.120 | $0.400 | **$0.520** |
| **Two Companies** | Matrix | $0.120 | $0.420 | **$0.540** |
| **Two Companies** | Deck (21 slides) | $0.120 | $0.522 | **$0.642** |
| **Three+ Companies** | Deck | $0.180+ | $0.700+ | **$0.880+** |

---

## Monthly Cost Projections

### Usage Scenarios

| Daily Usage | Query Type | Daily Cost | Monthly Cost (30 days) |
|-------------|------------|------------|------------------------|
| 10 queries | Single Company | $2.40 | **$72** |
| 10 queries | Two Company Deck | $6.42 | **$193** |
| 50 queries | Single Company | $12.00 | **$360** |
| 50 queries | Two Company Deck | $32.10 | **$963** |
| 100 queries | Mixed (70/30) | $36.12 | **$1,084** |

---

## Cost Optimization Strategies

### 1. **Caching Implementation**
- Cache Tavily search results for 24 hours
- Potential savings: **40-60%** on repeated company queries
- Implementation: Redis cache with company name as key

### 2. **Batch Processing**
- Use Claude's batch API for 50% discount
- Suitable for: Non-urgent analysis, bulk reports
- Potential savings: **$0.32 per two-company deck**

### 3. **Smart Model Selection**
- Use GPT-4o-mini for simple extractions
- Reserve Claude Sonnet 4.5 for complex analysis
- Potential savings: **30-40%** on extraction costs

### 4. **Prompt Optimization**
- Reduce context window by summarizing search results first
- Combine multiple operations in single prompts
- Potential savings: **20-30%** on token costs

### 5. **Tavily Optimization**
- Use Basic search (1 credit) for known companies
- Advanced search only for unknowns
- Potential savings: **$0.030 per company**

---

## Fallback Cost Analysis

If Claude Sonnet 4.5 is unavailable and system falls back to GPT-4o:

| Operation | Claude Sonnet 4.5 | GPT-4o | Cost Difference |
|-----------|-----------------|--------|-----------------|
| Single Company | $0.180 | $0.220 | +22% |
| Two Company Deck | $0.522 | $0.640 | +23% |

If falling back to GPT-4o-mini (emergency mode):

| Operation | Claude Sonnet 4.5 | GPT-4o-mini | Cost Difference |
|-----------|-----------------|-------------|-----------------|
| Single Company | $0.180 | $0.012 | -93% |
| Two Company Deck | $0.522 | $0.035 | -93% |

*Note: GPT-4o-mini significantly reduces quality*

---

## Break-Even Analysis

### At Current Pricing:
- **$30/month Tavily Plan**: Break-even at 2,000 basic searches or 1,000 advanced searches
- **Claude API**: No monthly minimum, pure usage-based
- **Recommended Budget**: $200-500/month for moderate usage (50-100 queries/day)

### Cost per Value Delivered:
- **Cost per investment insight**: $0.64
- **Cost per company deep-dive**: $0.24
- **Cost per 21-slide deck**: $0.64
- **Human analyst equivalent**: $500-2000 (100-400x cost savings)

---

## Recommendations

1. **Implement Caching ASAP**: Biggest bang for buck, especially for popular companies
2. **Use Batch API**: For overnight reports and non-urgent analysis
3. **Monitor Usage**: Set up alerts at $50, $100, $200 thresholds
4. **Consider Enterprise Plans**: At >500 queries/day, negotiate enterprise pricing
5. **Optimize Prompts**: Current prompts use ~20K tokens, can reduce to ~12K with compression

---

*Last Updated: September 2025*
*Note: All costs are estimates based on typical token usage patterns*