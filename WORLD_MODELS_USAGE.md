# World Models - "Paint Your Scenarios" System

## Overview

The World Models system allows CFOs to **paint scenarios** on a visual canvas using natural language. Ask "what if" questions and see the impact on your portfolio in real-time.

## How It Works

### 1. Natural Language Scenario Composition

Type any "what if" question and the system will:
- Parse the query to extract events, entities, and timing
- Identify which factors are impacted
- Create a visual representation on the canvas
- Calculate the impact on your portfolio

### Examples

**Simple Event:**
```
What happens if growth decelerates in YX in year 2
```

**Multiple Events:**
```
What happens if growth decelerates in YX in year 2, but Tundex starts a commercial pilot with a tier 1 aerospace company
```

**Complex Scenario:**
```
What if YX growth slows in Q2 but Tundex gets a major partnership, while competitor Z launches a competing product
```

**Random Events:**
```
What happens if Acme Corp raises a Series B in Q3 2025, hires a new CTO, and opens an office in Europe
```

## API Endpoints

### Parse "What If" Query

```bash
POST /api/nl-scenarios/what-if
{
  "query": "What happens if growth decelerates in YX in year 2",
  "fund_id": "optional-fund-id"
}
```

Returns:
- Parsed events with entity names, event types, timing, and impact factors
- Ready to be painted on canvas

### Compose Scenario

```bash
POST /api/nl-scenarios/compose
{
  "query": "What happens if growth decelerates in YX in year 2",
  "model_id": "world-model-id",
  "fund_id": "optional-fund-id"
}
```

Returns:
- Created scenario in world model
- Execution results showing impact
- Factor changes and model outputs

## Frontend Usage

### Scenario Canvas Component

```tsx
import { ScenarioCanvas } from '@/components/world-models/ScenarioCanvas';

<ScenarioCanvas
  modelId="world-model-id"
  fundId="fund-id"
  onScenarioComposed={(scenario) => {
    console.log('Scenario composed:', scenario);
  }}
/>
```

### World Model Viewer

```tsx
import { WorldModelViewer } from '@/components/world-models/WorldModelViewer';

<WorldModelViewer
  modelId="world-model-id"
  fundId="fund-id"
/>
```

## Event Types Supported

1. **Growth Changes**
   - "growth decelerates", "growth accelerates", "revenue growth slows"
   - Impacts: growth_rate, revenue, revenue_projection, valuation

2. **Partnerships**
   - "starts a commercial pilot", "partners with", "signs a deal"
   - Impacts: revenue, competitive_position, market_sentiment

3. **Funding**
   - "raises funding", "closes a round", "gets investment"
   - Impacts: valuation, burn_rate, runway, market_sentiment

4. **Exits**
   - "gets acquired", "goes public", "exits via IPO"
   - Impacts: valuation, exit_value, DPI, TVPI

5. **Competitive**
   - "competitor enters", "market share drops"
   - Impacts: competitive_position, market_share, revenue

6. **Operational**
   - "hires key executive", "opens office", "expands to"
   - Impacts: execution_quality, team_quality, burn_rate

7. **Regulatory**
   - "regulatory approval", "gets approved by FDA"
   - Impacts: market_sentiment, operational_efficiency

## Timing Patterns

The system recognizes:
- "in year 2", "by Q3 2025", "in 6 months"
- "next year", "this quarter"
- Relative timing: "in 2 years", "within 3 months"

## Visual Canvas Features

1. **Drag & Drop**: Move events around the canvas
2. **Color Coding**: Different event types have different colors
3. **Impact Visualization**: See which factors are affected
4. **Real-time Composition**: Parse and compose scenarios instantly

## Integration with World Models

Scenarios are automatically:
1. Parsed from natural language
2. Converted to factor overrides in the world model
3. Executed to calculate impact
4. Stored for comparison and analysis

## Next Steps

1. Build a company world model:
```bash
POST /api/world-models/build-company-model
{
  "company_data": { ... },
  "fund_id": "..."
}
```

2. Ask "what if" questions:
```bash
POST /api/nl-scenarios/what-if
{
  "query": "your question here"
}
```

3. Compose and execute:
```bash
POST /api/nl-scenarios/compose
{
  "query": "your question here",
  "model_id": "..."
}
```

## Advanced: Custom Event Types

You can extend the system by:
1. Adding new event patterns to `EVENT_PATTERNS` in `nl_scenario_composer.py`
2. Adding impact calculations in `_calculate_event_impact`
3. Defining new factor relationships

## Example Workflow

1. **Create World Model** for your portfolio
2. **Type a question**: "What happens if YX growth slows but Tundex gets a tier 1 partnership"
3. **Parse & Paint**: Events appear on canvas as draggable cards
4. **Compose Scenario**: System calculates impact on all factors
5. **View Results**: See how valuation, NAV, and other metrics change
6. **Compare Scenarios**: Run multiple scenarios and compare

This is your "Leonardo canvas" - paint any scenario you can imagine!
