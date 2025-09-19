# Testing Spreadsheet Agent with Clickable Citations and Charts

## Step 1: Start the application
```bash
cd frontend
npm run dev
```

## Step 2: Navigate to Management Accounts
Open http://localhost:3001/management-accounts

## Step 3: Test Grid API manually in browser console

Open browser console (F12) and run:

```javascript
// Test basic writing
grid.write("A1", "Company", {style: {bold: true, backgroundColor: "#f3f4f6"}})
grid.write("B1", "Revenue 2024", {style: {bold: true, backgroundColor: "#f3f4f6"}})
grid.write("C1", "Growth Rate", {style: {bold: true, backgroundColor: "#f3f4f6"}})

// Test with citations (clickable)
grid.write("A2", "Stripe", {href: "https://stripe.com", source: "Company Website"})
grid.write("B2", 450000000, {href: "https://techcrunch.com/2024/stripe-revenue", source: "TechCrunch Nov 2024"})
grid.write("C2", 0.45, {href: "https://bloomberg.com/stripe-growth", source: "Bloomberg"})

grid.write("A3", "Square", {href: "https://square.com", source: "Company Website"})
grid.write("B3", 380000000, {href: "https://sec.gov/square", source: "SEC Filing"})
grid.write("C3", 0.38)

grid.write("A4", "Adyen", {href: "https://adyen.com", source: "Company Website"})
grid.write("B4", 290000000, {href: "https://forbes.com/adyen", source: "Forbes"})
grid.write("C4", 0.52)

// Test formulas
grid.formula("B5", "=SUM(B2:B4)")
grid.write("A5", "Total")

// Test formatting
grid.format("B2", "currency")
grid.format("B3", "currency")
grid.format("B4", "currency")
grid.format("B5", "currency")
grid.format("C2", "percentage")
grid.format("C3", "percentage")
grid.format("C4", "percentage")

// Test chart creation
grid.createChart("bar", {
  range: "A2:B4",
  title: "Revenue Comparison 2024"
})
```

## Step 4: Test Agent Flow

In the Agent Runner panel on the right, enter:

```
Analyze @Stripe, @Square, and @Adyen financial metrics with revenue growth projections and market share. Create comprehensive analysis with waterfall and bar charts showing revenue comparison.
```

Click the Play button to run the agent.

## Expected Results:

1. **Grid Population**: Agent should write data to the spreadsheet cells
2. **Clickable Citations**: Blue hyperlinked values that open source URLs when clicked
3. **Formulas**: Calculated cells using Excel-like formulas
4. **Charts**: Visual charts appearing in the right panel
5. **Formatting**: Currency and percentage formatting applied

## Verification Checklist:

- [ ] Grid cells are populated with data
- [ ] Values with citations appear as blue links
- [ ] Clicking citations opens the source URL in new tab
- [ ] Formulas calculate correctly
- [ ] Charts render in the chart panel
- [ ] Agent execution completes without errors

## Troubleshooting:

If agent doesn't write to grid:
1. Check browser console for errors
2. Verify `window.grid` is available
3. Check that commands are being executed

If citations aren't clickable:
1. Check that cells have `sourceUrl` property
2. Verify the link rendering logic in EnhancedSpreadsheet

If charts don't appear:
1. Check that chartData state is being set
2. Verify SpreadsheetChart component is imported
3. Check for console errors during chart creation