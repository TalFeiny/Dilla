# API Wiring Fix Plan - Output Format Handlers

## Problem Statement
The deck page and other output format pages are showing "Failed to generate. Backend returned no data" because of mismatched data structures between backend skill execution and frontend format handlers.

## Root Causes
1. **Backend Issue**: Skills return nested structures like `{"deck": {"slides": slides}}` 
2. **Streaming Issue**: The streaming response doesn't properly extract skill results
3. **Frontend Issue**: Format handlers expect different data paths than what backend provides
4. **Data Flow Issue**: Missing proper transformation layer between backend and frontend

## Complete Fix Strategy

### 1. Backend Fixes (`unified_mcp_orchestrator.py`)

#### Current Issues:
- `_execute_deck_generation` returns: `{"deck": {"slides": slides}}`
- `_execute_excel_generation` returns inconsistent structure
- `_execute_memo_generation` returns nested format
- No standardized output format across skills

#### Required Changes:
```python
# Deck Generation - Line ~1850
async def _execute_deck_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... existing logic ...
    return {
        "format": "deck",
        "slides": slides,
        "slide_count": len(slides),
        "theme": "professional",
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "company_count": len(companies)
        }
    }

# Excel Generation
async def _execute_excel_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... existing logic ...
    return {
        "format": "spreadsheet",
        "commands": commands,
        "metadata": {
            "rows": row_count,
            "columns": column_count
        }
    }

# Memo Generation
async def _execute_memo_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... existing logic ...
    return {
        "format": "docs",
        "sections": sections,
        "metadata": {
            "word_count": word_count,
            "section_count": len(sections)
        }
    }
```

### 2. Streaming Response Fix (`unified_brain.py`)

#### Current Issue:
The streaming response in lines 100-150 doesn't properly extract nested skill results.

#### Required Changes:
```python
# In the streaming handler, when processing skill results:
if event_type == "complete":
    skill_result = data.get("result", {})
    
    # Extract based on skill type
    if skill == "deck-storytelling":
        # Handle both nested and direct structure
        if "deck" in skill_result:
            final_result = {
                "format": "deck",
                "slides": skill_result["deck"].get("slides", []),
                **skill_result["deck"]
            }
        else:
            final_result = skill_result
    elif skill == "excel-generator":
        if "spreadsheet" in skill_result:
            final_result = {
                "format": "spreadsheet",
                "commands": skill_result["spreadsheet"].get("commands", []),
                **skill_result["spreadsheet"]
            }
        else:
            final_result = skill_result
    # ... similar for other formats
```

### 3. Frontend Route Fix (`route.ts`)

The route is mostly correct but needs better error handling:
```typescript
// Add validation before forwarding
if (!response.ok) {
    const errorText = await response.text();
    console.error('[unified-brain route] Backend error:', errorText);
    return NextResponse.json(
        { 
            error: 'Backend request failed', 
            details: errorText,
            format: body.outputFormat 
        },
        { status: response.status }
    );
}
```

### 4. Format Handler Updates

#### deck-handler.ts
```typescript
// Line 19-30 - Handle multiple data structures
if (parsedData) {
    // Try multiple paths
    const slides = 
        parsedData.slides ||                    // Direct structure
        parsedData.deck?.slides ||             // Nested in deck
        parsedData.result?.slides ||           // In result
        parsedData.result?.deck?.slides ||     // Nested in result.deck
        [];
    
    if (slides.length > 0) {
        console.log('[DeckHandler] Found slides:', slides.length);
        // Process slides...
    }
}
```

#### spreadsheet-handler.ts
```typescript
// Similar pattern for commands
const commands = 
    parsedData.commands ||
    parsedData.spreadsheet?.commands ||
    parsedData.result?.commands ||
    parsedData.result?.spreadsheet?.commands ||
    [];
```

#### docs-handler.ts
```typescript
// For document sections
const sections = 
    parsedData.sections ||
    parsedData.memo?.sections ||
    parsedData.docs?.sections ||
    parsedData.result?.sections ||
    [];
```

#### matrix-handler.ts
```typescript
// For matrix data
const matrixData = 
    parsedData.matrix ||
    parsedData.matrix_data?.matrix ||
    parsedData.result?.matrix ||
    parsedData.result?.matrix_data ||
    {};
```

### 5. Frontend Page Fixes

#### deck-agent/page.tsx (Lines 420-460)
```typescript
case 'complete':
    // Extract deck data with multiple fallbacks
    let deck = null;
    
    // Try different data paths
    if (data.result) {
        if (data.result.format === 'deck' && data.result.slides) {
            // Direct format
            deck = {
                id: `deck-${Date.now()}`,
                title: data.result.metadata?.title || 'Investment Analysis',
                type: selectedTemplate || 'pitch',
                slides: data.result.slides,
                theme: data.result.theme,
                citations: data.result.citations || []
            };
        } else if (data.result.deck?.slides) {
            // Nested structure
            deck = {
                id: `deck-${Date.now()}`,
                title: 'Investment Analysis',
                type: selectedTemplate || 'pitch',
                ...data.result.deck
            };
        } else if (Array.isArray(data.result.slides)) {
            // Direct slides array
            deck = {
                id: `deck-${Date.now()}`,
                title: 'Investment Analysis',
                type: selectedTemplate || 'pitch',
                slides: data.result.slides
            };
        }
    }
    
    if (!deck || !deck.slides || deck.slides.length === 0) {
        console.error('[Deck Agent] No valid deck data found in:', data);
        throw new Error('No deck data in response');
    }
    
    setCurrentDeck(deck);
    break;
```

### 6. Comprehensive Logging Strategy

Add debug logging at each layer:

#### Backend:
```python
logger.info(f"[{skill}] Returning structure: {list(result.keys())}")
logger.debug(f"[{skill}] Full result: {json.dumps(result, default=str)[:500]}")
```

#### Streaming:
```python
logger.info(f"Streaming event: {event_type} for skill: {skill}")
```

#### Frontend:
```typescript
console.log('[Format Handler] Received data structure:', Object.keys(parsedData));
console.log('[Format Handler] Data sample:', JSON.stringify(parsedData).slice(0, 200));
```

## Testing Plan

### Test Commands:
1. **Deck**: "Create a pitch deck for @Ramp"
2. **Spreadsheet**: "Create a comparison spreadsheet for @Deel @Mercury @Brex"
3. **Docs**: "Write an investment memo for @Anthropic"
4. **Matrix**: "Create a comparison matrix for @Toast @Veeva @Procore"

### Validation Checklist:
- [ ] Backend returns consistent format structure
- [ ] Streaming properly extracts skill results
- [ ] Format handlers find data regardless of nesting
- [ ] Frontend pages display content correctly
- [ ] Error messages are informative
- [ ] All 4 formats work end-to-end

## Implementation Status ✅

### Completed Tasks:
1. ✅ **Backend Return Structures Fixed**
   - `_execute_deck_generation` now returns standardized format
   - `_execute_excel_generation` returns proper spreadsheet format
   - `_execute_memo_generation` returns docs format correctly
   - All skills return consistent `{format: type, ...data}` structure

2. ✅ **Format Methods Updated**
   - `_format_deck` checks for skill-generated data first
   - `_format_spreadsheet` uses skill data when available
   - Fallback generation methods remain for backward compatibility

3. ✅ **Frontend Handlers Updated**
   - All 4 handlers now check multiple JSON paths
   - deck-handler.ts: Checks slides in 5+ locations
   - spreadsheet-handler.ts: Finds commands flexibly
   - docs-handler.ts: Extracts sections from any nesting
   - matrix-handler.ts: Handles matrix data robustly

4. ✅ **Frontend Pages Fixed**
   - deck-agent/page.tsx extracts slides from any structure
   - Handles both streaming and non-streaming responses
   - Proper error handling for missing data

## Testing Commands
Test each format with these commands:
```bash
# Deck format
"Create a pitch deck for @Ramp"

# Spreadsheet format  
"Create a comparison spreadsheet for @Deel @Mercury @Brex"

# Docs format
"Write an investment memo for @Anthropic"

# Matrix format
"Create a comparison matrix for @Toast @Veeva @Procore"
```

## Success Metrics
- ✅ All 4 output format pages load without errors
- ✅ Data flows correctly from backend to frontend
- ✅ System handles multiple JSON structures
- ✅ Backward compatibility maintained

## Rollback Plan
If issues arise:
1. Keep old data paths as fallbacks
2. Add feature flags for new structure
3. Log both old and new format attempts
4. Gradually migrate to new structure

---
*Last Updated: 2025-09-20*
*Status: Ready for Implementation*