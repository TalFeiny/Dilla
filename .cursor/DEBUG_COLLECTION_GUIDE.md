# Debug Collection Guide

## Server Status
✅ Dev server is running on http://localhost:3001

## Steps to Collect Debug Information

### 1. Open Browser Developer Tools
- Navigate to http://localhost:3001/signin
- Open Developer Tools (F12 or Cmd+Option+I on Mac)
- Go to the **Console** tab

### 2. Look for Debug Logs
All debug logs are prefixed with `[DEBUG]`. You should see logs from:
- `RootLayout` - Layout initialization and CSS loading
- `AppShell` - Route detection and sidebar logic
- `SignInPage` - Page component mount
- `SignInContent` - Content component mount, CSS classes, hydration status

### 3. Check for Errors
Look for:
- **Hydration errors** - React hydration mismatches
- **CSS loading errors** - Failed stylesheet requests
- **JavaScript errors** - Runtime errors preventing rendering
- **Network errors** - Failed resource requests

### 4. Access Debug Data
The debug utility stores logs in `window.__debugLogs` and errors in `window.__debugErrors`.

In the console, run:
```javascript
// View all debug logs
console.table(window.__debugLogs || []);

// View all errors
console.table(window.__debugErrors || []);

// Export logs as JSON
JSON.stringify(window.__debugLogs || [], null, 2);
```

### 5. Network Tab Analysis
- Open the **Network** tab
- Filter by "CSS" or "stylesheet"
- Verify `globals.css` or Next.js CSS files are loading (status 200)
- Check for any failed requests (status 4xx or 5xx)

### 6. Elements Tab Analysis
- Inspect the signin page elements
- Check if elements have CSS classes applied
- Verify computed styles are being applied
- Look for `data-debug` attributes on elements

## What to Look For

### Hypothesis A: React Hydration Failure
**Evidence:**
- Console shows "Hydration failed" or "Hydration mismatch" errors
- `SignInContent` logs show `hasReact: false`
- React DevTools shows no component tree

### Hypothesis B: CSS/Tailwind Not Loading
**Evidence:**
- `RootLayout` logs show `hasGlobalsCSS: false` or `stylesheetCount: 0`
- Network tab shows failed CSS requests
- Computed styles show default browser styles (not Tailwind)
- `SignInContent` CSS check shows empty or missing classes

### Hypothesis C: Build/Compilation Error
**Evidence:**
- Server logs show TypeScript or build errors
- Browser console shows module resolution errors
- Page returns 500 error or shows error page

### Hypothesis D: JavaScript Runtime Error
**Evidence:**
- Console shows JavaScript errors
- `window.__debugErrors` contains entries
- Components fail to mount (no mount logs)

### Hypothesis E: AppShell/Layout Interference
**Evidence:**
- `AppShell` logs show incorrect route detection
- Sidebar is visible when it shouldn't be
- Layout providers are causing errors
- Children are not rendering

## Next Steps
After collecting logs, share:
1. Console output (all `[DEBUG]` logs)
2. Any errors from `window.__debugErrors`
3. Network tab screenshot (CSS requests)
4. Elements tab inspection results

