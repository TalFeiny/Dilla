
> all we are asking is for claude to pick the right one
  once its made that choice

⏺ You're absolutely right. Claude should be able to pick the right company from the search results. Let me see where
  that decision happens:

⏺ Search(pattern: "_extract_comprehensive_profile.*async def", path: "backend/app/services/unified_mcp_orchestrator.py",
         output_mode: "content")
  ⎿  Found 0 lines 

> ld only search for the company that it thinks it is

⏺ Exactly! Once Claude picks which company it thinks is the right VC-backed one, it should ONLY extract data about THAT
  company. Let me trace where this decision is made:

⏺ Search(pattern: "comprehensive_profile.*await", path: "backend/app/services/unified_mcp_orchestrator.py", output_mode:
         "content")
  ⎿  Found 5 lines (ctrl+r to expand)

⏺ Read(backend/app/services/unified_mcp_orchestrator.py)
  ⎿  Read 50 lines (ctrl+r to expand)

⏺ So this method sends ALL search results to Claude. Let me see the Claude prompt that asks it to pick the right one:

⏺ Read(backend/app/services/unified_mcp_orchestrator.py)
  ⎿  Read 50 lines (ctrl+r to expand)

⏺ This is good - it tells Claude to filter for VC-backed companies (lines 3215-3226). But then this extracted profile
  goes to StructuredDataExtractor which runs a DIFFERENT Claude call without these instructions.

  Let me trace the flow:

⏺ Read(backend/app/services/unified_mcp_orchestrator.py)
  ⎿  Read 10 lines (ctrl+r to expand)

> it should actually do another search once it has decided the right company

> so as to exclude noise

⏺ YES! That's the solution!

  Current flow:
  1. Search for "Howie" → Gets mixed results (Airtable CEO + Howie Systems + random businesses)
  2. Claude tries to pick the VC-backed one from noise
  3. But all the noise is still there

  Better flow:
  1. Initial search for "Howie"
  2. Claude identifies the RIGHT company (e.g., "Howie Systems, Polish PropTech startup")
  3. Do a SECOND, targeted search with more specific terms like:
    - "Howie Systems Poland PropTech"
    - "Howie Systems €420,000 funding"
    - Exclude the wrong ones: -Airtable -"Howie Liu"
  4. Now extract from clean, targeted results

  This would eliminate the noise and give Claude clean data about just the right company!

╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Ready to code?                                                                                                            │
│                                                                                                                           │
│ Here is Claude's plan:                                                                                                    │
│ ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ Solution: Two-Stage Search with Disambiguation                                                                        │ │
│ │                                                                                                                       │ │
│ │ The Problem                                                                                                           │ │
│ │                                                                                                                       │ │
│ │ Claude gets mixed search results (multiple companies with similar names) and struggles to extract clean data from the │ │
│ │  noise.                                                                                                               │ │
│ │                                                                                                                       │ │
│ │ The Fix: Add a Second Targeted Search                                                                                 │ │
│ │                                                                                                                       │ │
│ │ Stage 1: Initial Search & Identification                                                                              │ │
│ │                                                                                                                       │ │
│ │ 1. Search broadly for "@CompanyName"                                                                                  │ │
│ │ 2. Claude identifies which is the VC-backed startup from results                                                      │ │
│ │ 3. Extract key identifiers:                                                                                           │ │
│ │   - Full company name                                                                                                 │ │
│ │   - Location/geography                                                                                                │ │
│ │   - Sector/industry                                                                                                   │ │
│ │   - Key funding details                                                                                               │ │
│ │   - What to EXCLUDE (wrong companies found)                                                                           │ │
│ │                                                                                                                       │ │
│ │ Stage 2: Targeted Search                                                                                              │ │
│ │                                                                                                                       │ │
│ │ Once Claude picks the right company, do a NEW search:                                                                 │ │
│ │ - Include specific identifiers: "CompanyName location sector"                                                         │ │
│ │ - Include unique details: funding amounts, investor names                                                             │ │
│ │ - EXCLUDE wrong matches: -wrongcompany -"wrong CEO name"                                                              │ │
│ │ - Search for the identified website directly                                                                          │ │
│ │                                                                                                                       │ │
│ │ Stage 3: Clean Extraction                                                                                             │ │
│ │                                                                                                                       │ │
│ │ Now extract from the clean, targeted results without noise                                                            │ │
│ │                                                                                                                       │ │
│ │ Implementation Points                                                                                                 │ │
│ │                                                                                                                       │ │
│ │ - After _extract_comprehensive_profile identifies the company                                                         │ │
│ │ - Before sending to StructuredDataExtractor                                                                           │ │
│ │ - Use the profile details to build targeted search queries                                                            │ │
│ │ - This ensures Claude only sees data about the RIGHT company                                                          │ │
│ │                                                                                                                       │ │
│ │ This eliminates noise and ensures clean, accurate data extraction.                                                    │ │
│ ╰──────────────────────────────────────────────────────────────────────────