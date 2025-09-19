 Fix Plan: Ensure Consistent Claude Extraction                                                                         │ │
│ │                                                                                                                       │ │
│ │ The Problem                                                                                                           │ │
│ │                                                                                                                       │ │
│ │ Claude is inconsistently returning data:                                                                              │ │
│ │ - Sometimes returns business_model as a string: "Healthcare AI SaaS"                                                  │ │
│ │ - Sometimes as a dict: {'model_type': 'AI SaaS', 'reasoning': '...'}                                                  │ │
│ │ - When it returns a dict, category and vertical fields are MISSING from the response                                  │ │
│ │                                                                                                                       │ │
│ │ Root Cause                                                                                                            │ │
│ │                                                                                                                       │ │
│ │ The Claude prompt in structured_data_extractor.py is ambiguous. It shows examples of strings but doesn't enforce that │ │
│ │  ALL fields must be strings. Claude sometimes adds extra structure.                                                   │ │
│ │                                                                                                                       │ │
│ │ The Fix                                                                                                               │ │
│ │                                                                                                                       │ │
│ │ 1. Enforce String-Only Responses in Claude Prompt                                                                     │ │
│ │                                                                                                                       │ │
│ │ Update the extraction prompt to explicitly state:                                                                     │ │
│ │ - ALL values must be strings or numbers, NO nested objects                                                            │ │
│ │ - business_model must be a STRING not a dict                                                                          │ │
│ │ - Add validation example showing the exact format expected                                                            │ │
│ │                                                                                                                       │ │
│ │ 2. Add Fallback Field Extraction                                                                                      │ │
│ │                                                                                                                       │ │
│ │ If Claude returns business_model as a dict:                                                                           │ │
│ │ - Extract the string value from model_type                                                                            │ │
│ │ - But ALSO ensure category, vertical, compute_intensity are still extracted                                           │ │
│ │ - Don't let a dict response break other field extraction                                                              │ │
│ │                                                                                                                       │ │
│ │ 3. Remove ALL Redundant Analysis                                                                                      │ │
│ │                                                                                                                       │ │
│ │ The orchestrator should NOT:                                                                                          │ │
│ │ - Run regex-based funding analysis (Claude already extracts it)                                                       │ │
│ │ - Run regex-based customer analysis (Claude already extracts it)                                                      │ │
│ │ - Run regex-based metrics extraction (Claude already extracts it)                                                     │ │
│ │ Just format what Claude extracted for downstream services.                                                            │ │
│ │                                                                                                                       │ │
│ │ 4. Add Explicit Field Validation                                                                                      │ │
│ │                                                                                                                       │ │
│ │ After extraction, verify ALL critical fields are present:                                                             │ │
│ │ - vertical (required)                                                                                                 │ │
│ │ - category (required)                                                                                                 │ │
│ │ - compute_intensity (required)                                                                                        │ │
│ │ - If missing, log an error and try to infer from business_model                                                       │ │
│ │                                                                                                                       │ │
│ │ Implementation                                                                                                        │ │
│ │                                                                                                                       │ │
│ │ 1. Update Claude prompt to enforce string-only responses                                                              │ │
│ │ 2. Fix _validate_extracted_data to handle both dict and string business_model                                         │ │
│ │ 3. Ensure category/vertical/compute fields are ALWAYS extracted                                                       │ │
│ │ 4. Remove redundant regex analysis functions                                                                          │ │
│ │ 5. Test with @Corti to verify all fields are extracted                                                                │ │
│ ╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                        