# TypeScript Errors - Recurring Issues and Fixes

## Date: 2025-09-11

### Problem
The frontend build completes successfully but skips TypeScript validation, leading to runtime errors when pages try to load. The build shows:
```
✓ Compiled successfully
Skipping validation of types
Skipping linting
```

### Root Causes

#### 1. Supabase Client API Changes
**Error:** `Property 'table' does not exist on type 'SupabaseClient'`

**Files Affected:**
- `/src/app/api/agent/feedback/route.ts`
- `/src/app/api/agent/unified-brain/save-to-supabase.ts`

**Fix:** Replace `.table()` with `.from()`:
```typescript
// OLD (incorrect)
await supabase.table('table_name')

// NEW (correct)
await supabase.from('table_name')
```

#### 2. Type Assertion Issues
**Error:** `Argument of type 'unknown' is not assignable to parameter of type 'SetStateAction<string>'`

**File:** `/src/app/fund_admin/page.tsx` (lines 348, 350)

**Fix:** Add type assertions:
```typescript
// OLD
setActiveTaskId(fundData.taskId);

// NEW
setActiveTaskId(fundData.taskId as string);
```

#### 3. Missing Property Checks
**Error:** `Property 'taskId' does not exist on type`

**Fix:** Use `in` operator for runtime checks:
```typescript
if ('taskId' in fundData && fundData.taskId) {
  setActiveTaskId(fundData.taskId as string);
}
```

### Quick Fix Commands

1. **Find all Supabase table() usage:**
```bash
grep -r "\.table(" src/
```

2. **Check TypeScript errors without building:**
```bash
npx tsc --noEmit
```

3. **Run with type checking enabled:**
```bash
# Edit next.config.mjs to enable type checking
typescript: {
  ignoreBuildErrors: false
}
```

### Permanent Solution

1. **Update tsconfig.json** to enforce stricter checking:
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true
  }
}
```

2. **Add pre-commit hook** to catch errors:
```bash
npm install --save-dev husky
npx husky add .husky/pre-commit "npx tsc --noEmit"
```

3. **Update all Supabase client usage** to use the correct API:
- Search for `.table(` and replace with `.from(`
- Ensure all async operations have proper error handling
- Add type guards for unknown response types

### Current Status
- Fixed Supabase API calls in feedback and save-to-supabase routes
- Fixed type assertions in fund_admin page
- Dev server runs but may still have runtime errors on specific pages

### To Monitor
- Check browser console for runtime errors
- Watch for pages that fail to load completely
- Monitor Next.js build output for skipped validations

### Prevention
- Always run `npx tsc --noEmit` before committing
- Don't rely on Next.js build success alone
- Test pages in browser after fixing TypeScript errors