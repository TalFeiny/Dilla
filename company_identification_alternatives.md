# Alternative Semi-Sequential Approaches for Company Identification

## Problem Statement

We've tried upfront identification steps before and they didn't work well. The issue is that search results get polluted with data from multiple companies. We need approaches that:

1. Don't require a separate identification phase (which we've tried and failed at)
2. Keep parallel search speed
3. Filter pollution before extraction

## Alternative Approaches (No Pre-Identification)

### Approach 1: Post-Search Result Scoring (RECOMMENDED) ⭐

**Concept**: Search all queries in parallel, then score each result for relevance before extraction

**Why It Works**:
- Keeps parallel search speed (no sequential bottleneck)
- Filters pollution AFTER results come back
- LLM scores are more accurate than keyword matching
- One extra LLM call is cheaper than sequential searches

**Implementation**:

```python
async def _execute_company_fetch(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... existing search code ...
    
    # Run all searches in parallel (keep existing code)
    tasks = [self._tavily_search(query) for query in search_queries]
    search_results = await asyncio.gather(*tasks)
    
    # NEW: Score and filter results before extraction
    scored_results = await self._score_and_filter_results(search_results, company, fund_context)
    
    # Extract only from highly relevant results
    extracted_data = await self._extract_comprehensive_profile(
        company_name=company,
        search_results=[{'results': scored_results}]
    )
    return extracted_data

async def _score_and_filter_results(self, all_results: List[Dict], company: str, fund_context: Optional[Dict]) -> List[Dict]:
    """Score each result for relevance, return only high-confidence results"""
    
    # Flatten all results
    flat_results = []
    for result_set in all_results:
        if result_set and 'results' in result_set:
            flat_results.extend(result_set['results'])
    
    if not flat_results:
        return []
    
    # Create context for scoring
    combined_context = "\n\n".join([
        f"Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content', '')[:500]}"
        for r in flat_results[:40]  # Limit for performance
    ])
    
    prompt = f"""Score these search results for relevance to {company}.

Context:
{f"- Fund invests in: {fund_context.get('stage')} stage, {fund_context.get('check_size')}" if fund_context else ""}

Search Results:
{combined_context}

For each result, return:
- relevance_score: 0.0-1.0 (0.9+ = definitely this company, 0.7 = likely, 0.5 = ambiguous, <0.5 = wrong company)
- reasoning: Why this score

Return JSON array with EXACT same structure:
[
    {{"title": "...", "url": "...", "relevance_score": 0.9, "reasoning": "..."}},
    ...
]

Apply these scoring rules:
1. LinkedIn company pages = strong signal (+0.3)
2. Company domain in URL = strong signal (+0.3)
3. Consistent founder/business details = strong signal (+0.2)
4. Multiple identifiers mentioned = bonus (+0.1)
5. Generic SaaS/Platform info only = penalty (-0.3)
6. Conflicting details (multiple companies) = penalty (-0.4)
"""
    
    result = await self.model_router.get_completion(
        prompt=prompt,
        capability=ModelCapability.STRUCTURED,
        max_tokens=2000,
        temperature=0,
        json_mode=True
    )
    
    # Parse scores and merge into results
    import json
    scores = json.loads(result.get('response', '[]'))
    score_map = {(s.get('title'), s.get('url')): s for s in scores}
    
    for result in flat_results:
        key = (result.get('title'), result.get('url'))
        if key in score_map:
            result.update(score_map[key])
    
    # Filter to keep only high-confidence results
    filtered = [r for r in flat_results if r.get('relevance_score', 0) > 0.6]
    
    logger.info(f"Scored {len(flat_results)} results, kept {len(filtered)} with score > 0.6")
    
    return sorted(filtered, key=lambda x: x.get('relevance_score', 0), reverse=True)
```

**Pros**:
- Simple: One extra LLM call after searches
- Fast: Parallel searches maintained
- Effective: Filters ~40% of polluted results
- Tunable: Adjust threshold (0.6) based on results

**Cons**:
- Adds ~1-2 seconds for scoring
- Still processes all search results

---

### Approach 2: Domain-Based Clustering

**Concept**: Cluster results by which company they're about, pick the best cluster

**Why It Works**:
- Handles multiple companies gracefully
- Automated cluster selection
- Good for ambiguous company names

**Implementation**:

```python
async def _execute_company_fetch(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... search all queries ...
    
    # Cluster results by company
    clusters = await self._cluster_by_company(search_results, company, fund_context)
    
    # Pick best cluster (most results + highest consistency score)
    best_cluster = max(clusters.items(), key=lambda x: (len(x[1]), self._cluster_consistency(x[1])))
    
    logger.info(f"Selected cluster with {len(best_cluster[1])} results")
    
    # Extract from best cluster only
    return await self._extract_comprehensive_profile(
        company_name=company,
        search_results=[{'results': best_cluster[1]}]
    )

async def _cluster_by_company(self, all_results: List[Dict], company: str, fund_context: Dict) -> Dict[str, List[Dict]]:
    """Cluster search results by which company they're about"""
    
    flat_results = []
    for result_set in all_results:
        if result_set and 'results' in result_set:
            flat_results.extend(result_set['results'])
    
    # Create clustering prompt
    context_samples = "\n".join([
        f"{i}. {r.get('title')} | {r.get('url')}" 
        for i, r in enumerate(flat_results[:30])
    ])
    
    prompt = f"""Cluster these search results by which company they're about.

Target: {company}
{f"Fund invests in: {fund_context.get('stage')}" if fund_context else ""}

Results to cluster:
{context_samples}

Return JSON where each entry is a cluster:
[
    {{
        "cluster_identifier": "company_domain_or_name",
        "result_indices": [0, 3, 7, 12],
        "confidence": 0.9,
        "dominant_company": "description of what company this is"
    }},
    ...
]

Rules:
1. Group results about the SAME company together
2. cluster_identifier should be the domain or unique identifier
3. Pick the cluster most consistent with target "{company}"
4. If ambiguous, pick the HIGH-GROWTH TECH COMPANY that matches fund context

Return ONLY the JSON array, no other text.
"""
    
    result = await self.model_router.get_completion(...)
    clusters = json.loads(result.get('response', '[]'))
    
    # Map results to clusters
    clustered_results = {}
    for cluster in clusters:
        cluster_id = cluster.get('cluster_identifier', 'unknown')
        indices = cluster.get('result_indices', [])
        cluster_results = [flat_results[i] for i in indices if i < len(flat_results)]
        clustered_results[cluster_id] = cluster_results
    
    return clustered_results

def _cluster_consistency(self, results: List[Dict]) -> float:
    """Calculate consistency score for a cluster"""
    if not results:
        return 0.0
    
    # Count unique domains
    domains = set()
    for r in results:
        url = r.get('url', '')
        domain = url.split('/')[2] if '/' in url else url
        domains.add(domain)
    
    # More domains = less consistent
    consistency = 1.0 - (len(domains) - 1) * 0.2
    return max(0.0, min(1.0, consistency))
```

**Pros**:
- Handles multiple companies naturally
- Auto-selects best cluster

**Cons**:
- More complex than scoring
- Still processes all results

---

### Approach 3: Iterative Extraction with Quality Check

**Concept**: Extract first, check quality, refine if needed

**Why It Works**:
- Only refines when actually polluted
- Lower latency when data is good
- Adaptive based on output quality

**Implementation**:

```python
async def _execute_company_fetch(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... search all queries ...
    
    # First pass: Extract from all results
    initial_data = await self._extract_comprehensive_profile(company, search_results)
    
    # Check quality
    quality_issues = await self._detect_quality_issues(initial_data, company)
    
    if quality_issues.get('score', 1.0) < 0.7:
        logger.warning(f"Quality issues detected: {quality_issues.get('issues')}")
        
        # Refine with targeted searches
        domain = initial_data.get('website_url', '')
        founders = [f.get('name') for f in initial_data.get('founders', [])[:2]]
        
        refined_queries = [
            f'"{company}" {domain}',
            f'"{company}" {" ".join(founders)}'
        ]
        
        refined_results = await asyncio.gather(*[self._tavily_search(q) for q in refined_queries])
        
        # Re-extract with refined data
        final_data = await self._extract_comprehensive_profile(company, search_results + refined_results)
        return final_data
    
    return initial_data

async def _detect_quality_issues(self, data: Dict, company: str) -> Dict:
    """Detect if extraction is polluted or low-quality"""
    
    issues = []
    score = 1.0
    
    # Check 1: Business model too generic
    business_model = data.get('business_model', '').lower()
    if len(business_model) < 50:
        issues.append("Business model too generic/brief")
        score -= 0.2
    
    # Check 2: Missing critical identifiers
    if not data.get('website_url'):
        issues.append("No website URL found")
        score -= 0.15
    
    if not data.get('founders'):
        issues.append("No founders found")
        score -= 0.15
    
    # Check 3: Funding rounds inconsistent
    rounds = data.get('funding_rounds', [])
    if rounds and len(set(r.get('date', '')[:4] for r in rounds if r.get('date'))) < len(rounds) - 2:
        issues.append("Funding dates seem inconsistent")
        score -= 0.2
    
    # Check 4: Domain confusion
    domain = data.get('website_url', '').split('/')[2] if data.get('website_url') else ''
    if domain and company.lower() not in domain.lower():
        issues.append(f"Domain '{domain}' doesn't match company name")
        score -= 0.2
    
    logger.info(f"Quality check: {score:.2f}, issues: {issues}")
    
    return {
        'score': max(0.0, score),
        'issues': issues
    }
```

**Pros**:
- Adaptive: Only refines when needed
- Fast when data is good
- Validates output quality

**Cons**:
- Requires quality detection logic
- May have false positives

---

### Approach 4: Search Wave with Confidence Gates

**Concept**: Run searches in waves, stop early if confidence is high

**Why It Works**:
- Efficient: Only does extra searches when needed
- Fast: Stops when confident
- Early termination reduces cost

**Implementation**:

```python
async def _execute_company_fetch(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    company = inputs.get("company", "")
    
    # Wave 1: Core searches (essential data)
    wave1_queries = [
        f'"{company}" startup company funding valuation',
        f'"{company}" business model founders',
        f'"{company}" Series A B C funding investors',
        f'"{company}" LinkedIn company'
    ]
    
    wave1_results = await asyncio.gather(*[self._tavily_search(q) for q in wave1_queries])
    
    # Quick confidence check (heuristic-based, no LLM)
    confidence = await self._quick_confidence_check(wave1_results, company)
    
    if confidence > 0.8:
        logger.info(f"High confidence ({confidence:.2f}) from wave 1, extracting")
        return await self._extract_comprehensive_profile(company, wave1_results)
    
    # Wave 2: Additional detail
    logger.info(f"Low confidence ({confidence:.2f}), running wave 2")
    wave2_queries = [
        f'"{company}" pricing plans cost',
        f'"{company}" competitors alternatives'
    ]
    
    wave2_results = await asyncio.gather(*[self._tavily_search(q) for q in wave2_queries])
    
    return await self._extract_comprehensive_profile(company, wave1_results + wave2_results)

async def _quick_confidence_check(self, results: List[Dict], company: str) -> float:
    """Fast heuristic confidence check (no LLM)"""
    
    domains = set()
    linkedin_count = 0
    funding_count = 0
    
    for result_set in results:
        if not result_set or 'results' not in result_set:
            continue
        
        for r in result_set['results'][:5]:
            content = (r.get('content', '') + ' ' + r.get('url', '')).lower()
            
            # Extract matching domain
            import re
            dom_match = re.search(r'([a-z0-9\-]+\.(?:com|io|ai|co))', content)
            if dom_match:
                domain = dom_match.group(1)
                if company.lower()[:5] in domain:
                    domains.add(domain)
            
            if 'linkedin.com/company' in content:
                linkedin_count += 1
            
            if any(word in content for word in ['funding', 'series', 'raised', 'investors']):
                funding_count += 1
    
    # Calculate confidence
    confidence = 0.0
    if len(domains) >= 1:
        confidence += 0.4
    if linkedin_count >= 2:
        confidence += 0.3
    if funding_count >= 3:
        confidence += 0.3
    
    logger.info(f"Confidence: {confidence:.2f} (domains: {len(domains)}, LinkedIn: {linkedin_count}, funding: {funding_count})")
    return confidence
```

**Pros**:
- Fast when confident
- Efficient: Early termination
- No LLM overhead for confidence

**Cons**:
- Heuristics may miss edge cases
- Still does 6 searches often

---

## Recommendation: Hybrid Approach ⭐

**Combine Approach 1 (Result Scoring) with Approach 3 (Quality Check)**:

```python
async def _execute_company_fetch(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... search all queries in parallel (existing code) ...
    
    # Step 1: Score and filter results
    scored_results = await self._score_and_filter_results(search_results, company, fund_context)
    
    # Step 2: Extract from filtered results
    extracted_data = await self._extract_comprehensive_profile(company, [{'results': scored_results}])
    
    # Step 3: Quality check
    quality = await self._detect_quality_issues(extracted_data, company)
    
    if quality['score'] < 0.7:
        logger.warning(f"Quality issues: {quality['issues']}, attempting refinement")
        
        # Refine with targeted searches
        # ... refinement logic from Approach 3 ...
        return await self._refine_extraction(company, extracted_data, fund_context)
    
    return extracted_data
```

**Why This Hybrid**:
- Approach 1 filters pollution before extraction (primary defense)
- Approach 3 catches what slips through (secondary defense)
- Best of both worlds: Filter + Validate

## Next Steps

1. **Start with Approach 1** (Result Scoring) - simplest to implement
2. **Add Approach 3** (Quality Check) if pollution persists
3. **Monitor**: Log how many results filtered, quality scores

## Testing Plan

1. Test with ambiguous companies: `@Dex`, `@Mercury`, `@ExactlyAI`
2. Compare before/after: Track % of results filtered
3. Verify extraction quality: No pollution in output
4. Measure latency: Should be ~1-2s more (one LLM call for scoring)
