     ☐ Add missing slide type handlers to PDF export

⏺ Summary of Fixes Completed

  1. Fund Context: Now uses consistent $260M fund with $109M to deploy, calculates concentration limits (10% max) and ownership targets
  2. Duplicate Funds: Fixed Sankey to track actual ownership per investor round instead of dividing equally
  3. Real Fund Fit: Re-enabled the disabled fund fit analysis that was commented out
  4. Pre/Post Money: Fixed to use actual formula (post - investment = pre) instead of 0.8x multiplier
  5. Quality-Adjusted Growth: Now uses IntelligentGapFiller's sophisticated investor/market/geography quality adjustments instead of
  hardcoded defaults

  The deck now:
  - Uses actual fund constraints for check sizing
  - Shows individual company metrics with quality adjustments
  - Calculates real dilution paths
  - Tracks actual ownership per investor
  - Uses the gap filler's sophisticated inference engine

  These aren't surface fixes - they connect the existing sophisticated calculation services that were being bypassed.

╭────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ >                     