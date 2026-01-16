# Hardcoded Values in Slide Generation

## Critical Hardcoded Values Found

### 1. TAM/Market Sizing (Lines 1241-1250)
```python
tam_by_sector = {
    "AI/ML": 500_000_000_000,  # $500B
    "Fintech": 300_000_000_000,  # $300B
    "Healthcare": 400_000_000_000,  # $400B
    "PropTech": 100_000_000_000,  # $100B
    "SaaS": 250_000_000_000,  # $250B
    "Technology": 200_000_000_000  # $200B default
}
```
**Issue**: Static TAM values instead of using calculated market_size from IntelligentGapFiller

### 2. Valuation/Revenue Scoring (Lines 1483-1486)
```python
val_score = min(float(valuation) / 1_000_000_000, 1.0) * 100  # Cap at $1B
rev_score = min(float(revenue) / 100_000_000, 1.0) * 100  # $100M is excellent
```
**Issue**: Fixed thresholds don't adapt to stage or fund size

### 3. AI/GPU Cost Analysis (Lines 1514-1534)
```python
base_check = 10_000_000  # $10M base for Series A
if existing_revenue > 50_000_000:  # Large SaaS
elif existing_revenue > 10_000_000:  # Mid-size
elif existing_revenue > 1_000_000:  # Small
```
**Issue**: Fixed revenue thresholds, should be stage-relative

### 4. Entry Point Analysis (Lines 1612-1614)
```python
"Growth stage entry. Typical $20-50M valuation"  # Series A
"Later stage, lower risk. Typical $100-200M valuation"  # Series B
```
**Issue**: Static valuation ranges instead of market-based

### 5. Cap Table Assumptions (Lines 3032-3033)
```python
f"Our $10M investment would give us ~{10_000_000/company1.get('valuation', 100_000_000)*100:.1f}%"
```
**Issue**: Hardcoded $10M check size instead of using optimal_check_size

### 6. Moat Scoring Thresholds (Lines 2435-2474)
```python
moat_scores['network_effects'] = min(9, 5 + (revenue / 10_000_000))
moat_scores['data_advantages'] = min(3, 1 + (revenue / 100_000_000))
moat_scores['economies_of_scale'] = min(8, 5 + (total_funding / 50_000_000))
if revenue > 100_000_000: moat_scores['brand_reputation'] = 8
```
**Issue**: Fixed revenue thresholds for moat scoring

### 7. Customer Segmentation (Lines 2153-2156)
```python
if revenue > 10_000_000: who_they_sell_to = "Enterprise customers"
elif revenue > 1_000_000: who_they_sell_to = "Mid-market companies"
```
**Issue**: Revenue-based customer assumptions instead of actual data

### 8. Market Dynamics Scoring (Lines 2379-2393)
```python
min(10, (market_size / 10_000_000_000) * 10)  # Market size score
```
**Issue**: Fixed $10B benchmark for market size

### 9. Default Valuations Throughout
```python
100_000_000  # Default $100M valuation used in 15+ places
1_000_000     # Default $1M revenue used in multiple places
20_000_000    # Default $20M funding used in several places
```

### 10. Fund Portfolio Analysis (Lines 5036-5039, 5089-5093)
```python
fund_size = context.get("fund_size", 456_000_000)  # $456M
remaining_capital = context.get("remaining_capital", 276_000_000)  # $276M
```
**Issue**: Different hardcoded defaults in different methods

## Impact Analysis

### High Priority (Affects fund decisions)
1. **Check sizes** - Should always use optimal_check_size from fund fit
2. **TAM values** - Should use calculated market_size from gap filler
3. **Valuation defaults** - Should use stage-appropriate benchmarks
4. **Customer segments** - Should use extracted data

### Medium Priority (Affects analysis quality)
5. **Moat scoring** - Should be relative to stage/sector
6. **Market scoring** - Should adapt to sector norms
7. **Revenue thresholds** - Should be stage-relative

### Low Priority (Cosmetic)
8. **Entry point descriptions** - Could be more dynamic
9. **Chart colors** - Acceptable as-is

## Recommended Fixes

### 1. Create Dynamic Defaults System
```python
def get_stage_defaults(stage: str, fund_size: float) -> Dict:
    """Get appropriate defaults based on stage and fund size"""
    # Returns valuation ranges, revenue benchmarks, etc.
```

### 2. Use Fund Context Throughout
- Every slide should pull from self.shared_data['fund_context']
- No slide should use hardcoded check sizes

### 3. Use Calculated Data
- TAM: Use company.get('market_size') from IntelligentGapFiller
- Valuations: Use company.get('inferred_valuation') with stage benchmarks
- Revenue: Use company.get('inferred_revenue') always

### 4. Make Thresholds Relative
- Moat scores relative to stage peers
- Market scores relative to sector norms
- Customer segments from actual extracted data