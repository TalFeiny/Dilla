Fix Plan for TAM Calculation NoneType Error                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ Problem                                                                                                                                │ │
│ │                                                                                                                                        │ │
│ │ The backend crashes with "unsupported operand type(s) for /: 'NoneType' and 'float'" when processing TAM calculations for companies,   │ │
│ │ causing the entire request to fail after 120 seconds.                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ Root Cause                                                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ In unified_mcp_orchestrator.py lines 1525-1527, the code tries to divide TAM/SAM/SOM values by 1e9 to format them in billions, but     │ │
│ │ these values can be None when market data extraction fails.                                                                            │ │
│ │                                                                                                                                        │ │
│ │ Fix                                                                                                                                    │ │
│ │                                                                                                                                        │ │
│ │ Add None checks before division operations in the TAM logging section:                                                                 │ │
│ │                                                                                                                                        │ │
│ │ 1. Line 1525: Check if tam_value is not None before dividing                                                                           │ │
│ │ 2. Line 1526: Check if sam_value is not None before dividing                                                                           │ │
│ │ 3. Line 1527: Check if som_value is not None before dividing                                                                           │ │
│ │                                                                                                                                        │ │
│ │ Changes Required                                                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ Replace the three problematic logger.info lines with safe versions that handle None values:                                            │ │
│ │ - Use a default value of 0 when the value is None                                                                                      │ │
│ │ - Or skip the division and show "N/A" for None values                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ This will prevent the crash and allow the request to complete successfully even when TAM data extraction fails.                        │ │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                                                                                                            │
│ Would you like to proceed?     