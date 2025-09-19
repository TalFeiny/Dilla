# Quick Agent Test

## 1. Open the page
http://localhost:3001/management-accounts

## 2. Clear any existing data
Click the trash icon in the toolbar (if there's data)

## 3. Test in browser console:
```javascript
// Test grid API exists
console.log('Grid API available:', !!window.grid);

// Write test data with citations
window.grid.write("A1", "Company", {style: {bold: true}});
window.grid.write("B1", "Revenue", {style: {bold: true}});
window.grid.write("A2", "Stripe", {href: "https://stripe.com"});
window.grid.write("B2", 450000000, {href: "https://techcrunch.com"});
window.grid.format("B2", "currency");

// Should see data in cells with Stripe as blue clickable link
```

## 4. Test Agent:
In the Agent Runner panel, type:
```
Create a simple revenue analysis for @Stripe with formulas
```

Click "Run Agent"

## Expected:
- Agent should write data to the grid
- Values with citations should be clickable (blue links)
- Formulas should calculate

## If not working, check console for:
- "Grid API: Wrote..." messages
- Any error messages
- Whether commands are being executed