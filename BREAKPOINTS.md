# Liquidation Preference Stack Breakpoints - How They Actually Work

## What Are Breakpoints?

Breakpoints are **valuation thresholds where the distribution mechanism changes** in a liquidation waterfall. They are NOT arbitrary multiples (2x, 3x) but rather the **inflection points** where:
- A class of shares switches from taking liquidation preference to converting to common
- The next tier in the preference stack starts receiving proceeds
- Participating preferred starts participating
- The marginal dollar changes who it goes to

## Key Breakpoint Types

### 1. Conversion Breakpoints
The most critical breakpoint for any series - where they switch from taking their liquidation preference to converting to common.

**Formula:**
```
Conversion Point = (Liquidation Preference × Multiple) / Ownership %
```

**Example:**
- Series B invested $10M at 20% ownership with 1x preference
- Conversion breakpoint = $10M / 0.20 = $50M
- Below $50M exit: Take the $10M preference
- Above $50M exit: Convert to common and take 20%

### 2. Stack Satisfaction Breakpoints
Points where each layer of the preference stack gets fully paid:

**Tranche 1:** $0 → Total Senior Debt
- Senior debt gets everything until satisfied

**Tranche 2:** Senior Debt → Senior Debt + Series C Preference  
- Series C starts getting paid

**Tranche 3:** Previous → Previous + Series B Preference
- Series B starts getting paid

And so on down the stack...

### 3. Participation Breakpoints
For participating preferred, there are multiple breakpoints:
- Initial preference satisfaction point
- Participation cap point (if capped)
- Conversion point (where converting beats participating)

## How Breakpoints Change with Future Rounds

### Current State (We just invested)
```
Stack Position: #1 (most senior)
Breakpoints:
- Our preference satisfied: $10M
- Our conversion point: $50M (10M / 20% ownership)
```

### After Series C Raises $30M
```
Stack Position: #2 (Series C is now senior)
New Breakpoints:
- Series C preference satisfied: $30M
- Our layer reached: $30M (we start getting paid)
- Our preference satisfied: $40M ($30M + $10M)
- Our conversion point: $80M (higher due to dilution)
```

### After Series D Raises $60M
```
Stack Position: #3 (D and C above us)
New Breakpoints:
- Series D satisfied: $60M
- Series C satisfied: $90M
- Our layer reached: $90M
- Our preference satisfied: $100M
- Our conversion point: $120M (even higher with more dilution)
```

## Why Breakpoints Matter More Than Scenarios

Instead of running expensive PWERM scenarios, breakpoints tell us:

1. **Minimum exit for returns**: The stack satisfaction point above us
2. **Optimal exit timing**: Before too many rounds push breakpoints too high
3. **Reserve requirements**: How much we need to maintain position as breakpoints shift
4. **Conversion strategy**: At what exit values we should convert vs. take preference

## Actionable Insights from Breakpoints

### For a Series B Investment:

**Without Follow-on:**
- Breakeven exit: $90M (after C and D take their preference)
- 2x exit: $180M
- Conversion beneficial: >$150M

**With Follow-on (maintain pro-rata):**
- Breakeven exit: $70M (less dilution, better position)
- 2x exit: $140M
- Conversion beneficial: >$120M

### Reserve Planning Based on Breakpoints:
- If next round pushes our breakeven from $50M → $90M
- And typical exit is $200M
- Then reserves are critical to maintain acceptable returns

## Implementation in Code

The key is to calculate breakpoints dynamically based on:
1. Current cap table
2. Expected future rounds (size, terms)
3. Quality-adjusted dilution rates
4. Investor tier effects on terms

NOT fixed assumptions like "18% dilution" or "we're always #1".

## The Core Insight

**Breakpoints show WHERE the economics change, not just WHAT the returns are.**

This makes them actionable because they reveal:
- Critical valuation thresholds
- When to push for exit vs. continue
- How much reserves really matter
- Why timing and stack position are everything