# Style Unification & Chart Rendering Fix Plan

## Goal
- **Unified style**: Inter font, consistent color scheme (like landing page)
- **Chart parity**: All slides and charts render in BOTH web and PDF
- **Proper formatting**: All $ values show as $XM, proper Y-axis labels
- **Charts actually work**: No missing/broken charts

---

## Part 1: Unified Style System

### 1.1 Create Shared Design Tokens
**File: `frontend/src/styles/deck-design-tokens.ts` (NEW)**

```typescript
export const DECK_DESIGN_TOKENS = {
  fonts: {
    primary: 'Inter, system-ui, -apple-system, sans-serif',
    mono: 'IBM Plex Mono, monospace',
  },
  
  colors: {
    // Primary brand colors
    primary: {
      50: '#f0f9ff',
      100: '#e0f2fe',
      200: '#bae6fd',
      300: '#7dd3fc',
      400: '#38bdf8',
      500: '#0ea5e9',
      600: '#0284c7',
      700: '#0369a1',
      800: '#075985',
      900: '#0c4a6e',
    },
    
    // Chart colors (professional palette)
    chart: [
      '#0ea5e9', // Blue
      '#8b5cf6', // Purple
      '#10b981', // Green
      '#f59e0b', // Orange
      '#ef4444', // Red
      '#06b6d4', // Cyan
      '#ec4899', // Pink
      '#6366f1', // Indigo
    ],
    
    // Semantic colors
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#0ea5e9',
    
    // Neutral colors
    gray: {
      50: '#f9fafb',
      100: '#f3f4f6',
      200: '#e5e7eb',
      300: '#d1d5db',
      400: '#9ca3af',
      500: '#6b7280',
      600: '#4b5563',
      700: '#374151',
      800: '#1f2937',
      900: '#111827',
    },
  },
  
  spacing: {
    slide: {
      padding: '3rem',
      titleMargin: '2rem',
      sectionMargin: '1.5rem',
    },
  },
  
  typography: {
    slideTitle: {
      fontSize: '2.5rem',
      fontWeight: 700,
      lineHeight: 1.2,
    },
    slideSubtitle: {
      fontSize: '1.25rem',
      fontWeight: 500,
      lineHeight: 1.4,
    },
    body: {
      fontSize: '1rem',
      fontWeight: 400,
      lineHeight: 1.6,
    },
    metric: {
      fontSize: '2rem',
      fontWeight: 700,
      lineHeight: 1.2,
    },
  },
};
```

### 1.2 Update Frontend Deck Styles
**File: `frontend/src/components/DeckSlide.tsx`**

```typescript
import { DECK_DESIGN_TOKENS } from '@/styles/deck-design-tokens';

const slideStyles = {
  fontFamily: DECK_DESIGN_TOKENS.fonts.primary,
  padding: DECK_DESIGN_TOKENS.spacing.slide.padding,
};

const titleStyles = {
  ...DECK_DESIGN_TOKENS.typography.slideTitle,
  color: DECK_DESIGN_TOKENS.colors.gray[900],
  marginBottom: DECK_DESIGN_TOKENS.spacing.slide.titleMargin,
};
```

### 1.3 Update PDF Export Styles
**File: `backend/app/services/deck_export_service.py`**
**Location: Lines 1337-1453 (the `<style>` section)**

```python
# REPLACE entire style section with:
def _get_unified_styles(self) -> str:
    """Get unified styles matching frontend design tokens"""
    return """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            font-feature-settings: 'kern' 1, 'liga' 1;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            background: #ffffff;
            color: #111827;
        }
        
        .slide {
            width: 1024px;
            min-height: 768px;
            padding: 3rem;
            page-break-after: always;
            page-break-inside: avoid;
            background: #ffffff;
            display: flex;
            flex-direction: column;
        }
        
        @media print {
            .slide {
                page-break-after: always;
                page-break-inside: avoid;
                border: none;
            }
        }
        
        /* Typography */
        .slide-title {
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1.2;
            color: #111827;
            margin-bottom: 2rem;
            letter-spacing: -0.02em;
        }
        
        .slide-subtitle {
            font-size: 1.25rem;
            font-weight: 500;
            line-height: 1.4;
            color: #4b5563;
            margin-bottom: 1.5rem;
        }
        
        .slide-body {
            font-size: 1rem;
            font-weight: 400;
            line-height: 1.6;
            color: #374151;
        }
        
        /* Metrics */
        .metric-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 0.75rem;
            padding: 1.5rem;
            text-align: center;
        }
        
        .metric-value {
            font-family: 'Inter', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            color: #0ea5e9;
            margin-bottom: 0.5rem;
            letter-spacing: -0.02em;
        }
        
        .metric-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Charts */
        .chart-container {
            position: relative;
            width: 100%;
            height: 400px;
            padding: 1rem;
            background: #fafbfc;
            border: 1px solid #e5e7eb;
            border-radius: 0.5rem;
        }
        
        /* Tables */
        .professional-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }
        
        .professional-table th {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #374151;
        }
        
        .professional-table td {
            border: 1px solid #e5e7eb;
            padding: 0.75rem;
            color: #4b5563;
        }
        
        /* Remove decorative fonts - professional only */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Inter', sans-serif;
        }
    """

# UPDATE _generate_html_deck method at line 1327:
html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Investment Analysis Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        {self._get_unified_styles()}
    </style>
</head>
<body>
    {''.join(slides_html)}
    <script>
        {self._generate_chart_scripts(deck_data)}
    </script>
</body>
</html>
"""
```

---

## Part 2: Number Formatting System

### 2.1 Create Unified Formatter
**File: `frontend/src/lib/formatters.ts` (NEW)**

```typescript
export class DeckFormatter {
  /**
   * Format currency values in millions
   * @example formatCurrency(5000000) => "$5.0M"
   * @example formatCurrency(500000) => "$0.5M"
   */
  static formatCurrency(value: number): string {
    if (value === null || value === undefined) return 'N/A';
    
    const millions = value / 1_000_000;
    
    if (millions >= 1000) {
      // Billions
      return `$${(millions / 1000).toFixed(1)}B`;
    } else if (millions >= 1) {
      // Millions
      return `$${millions.toFixed(1)}M`;
    } else if (millions >= 0.1) {
      // Show one decimal for < $1M
      return `$${millions.toFixed(1)}M`;
    } else {
      // Very small values - show in K
      return `$${(value / 1000).toFixed(0)}K`;
    }
  }
  
  /**
   * Format percentages
   * @example formatPercentage(0.156) => "15.6%"
   */
  static formatPercentage(value: number, decimals: number = 1): string {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(decimals)}%`;
  }
  
  /**
   * Format multiples
   * @example formatMultiple(12.5) => "12.5x"
   */
  static formatMultiple(value: number, decimals: number = 1): string {
    if (value === null || value === undefined) return 'N/A';
    return `${value.toFixed(decimals)}x`;
  }
  
  /**
   * Format Y-axis ticks for charts
   */
  static getYAxisFormatter(maxValue: number): (value: number) => string {
    return (value: number) => {
      if (maxValue >= 1_000_000) {
        return this.formatCurrency(value);
      } else if (maxValue >= 1000) {
        return `$${(value / 1000).toFixed(0)}K`;
      } else {
        return `$${value.toFixed(0)}`;
      }
    };
  }
}
```

### 2.2 Backend Formatter (Python)
**File: `backend/app/utils/formatters.py` (NEW)**

```python
"""
Unified formatting utilities for deck generation
"""

class DeckFormatter:
    """Format values consistently across deck"""
    
    @staticmethod
    def format_currency(value: float) -> str:
        """Format currency values in millions"""
        if value is None:
            return "N/A"
        
        millions = value / 1_000_000
        
        if millions >= 1000:
            # Billions
            return f"${millions/1000:.1f}B"
        elif millions >= 1:
            # Millions
            return f"${millions:.1f}M"
        elif millions >= 0.1:
            # Small millions
            return f"${millions:.1f}M"
        else:
            # Thousands
            return f"${value/1000:.0f}K"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """Format percentages"""
        if value is None:
            return "N/A"
        return f"{value * 100:.{decimals}f}%"
    
    @staticmethod
    def format_multiple(value: float, decimals: int = 1) -> str:
        """Format multiples"""
        if value is None:
            return "N/A"
        return f"{value:.{decimals}f}x"
    
    @staticmethod
    def format_chart_axis_value(value: float, max_value: float) -> str:
        """Format axis values based on scale"""
        if max_value >= 1_000_000:
            return DeckFormatter.format_currency(value)
        elif max_value >= 1000:
            return f"${value/1000:.0f}K"
        else:
            return f"${value:.0f}"
```

### 2.3 Apply Formatting to All Slides
**File: `backend/app/services/deck_generation_service.py`**

```python
from app.utils.formatters import DeckFormatter

# USE EVERYWHERE:
# Instead of: f"${revenue}"
# Use: DeckFormatter.format_currency(revenue)

# Instead of: f"{ownership}%"
# Use: DeckFormatter.format_percentage(ownership / 100)

# Instead of: f"{multiple}x"
# Use: DeckFormatter.format_multiple(multiple)
```

---

## Part 3: Chart Configuration Unification

### 3.1 Unified Chart Options
**File: `frontend/src/lib/chart-config.ts` (NEW)**

```typescript
import { ChartOptions } from 'chart.js';
import { DECK_DESIGN_TOKENS } from '@/styles/deck-design-tokens';
import { DeckFormatter } from './formatters';

export function getUnifiedChartOptions(
  maxValue: number,
  yAxisLabel?: string
): ChartOptions {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          padding: 16,
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 12,
            weight: '500',
          },
          color: DECK_DESIGN_TOKENS.colors.gray[700],
          usePointStyle: true,
        },
      },
      tooltip: {
        backgroundColor: DECK_DESIGN_TOKENS.colors.gray[900],
        titleFont: {
          family: DECK_DESIGN_TOKENS.fonts.primary,
          size: 13,
          weight: '600',
        },
        bodyFont: {
          family: DECK_DESIGN_TOKENS.fonts.primary,
          size: 12,
        },
        padding: 12,
        cornerRadius: 6,
        callbacks: {
          label: (context) => {
            const value = context.parsed.y;
            return `${context.dataset.label}: ${DeckFormatter.formatCurrency(value)}`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: DECK_DESIGN_TOKENS.colors.gray[200],
          drawBorder: false,
        },
        ticks: {
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 11,
          },
          color: DECK_DESIGN_TOKENS.colors.gray[600],
          callback: function(value) {
            return DeckFormatter.getYAxisFormatter(maxValue)(value as number);
          },
        },
        title: {
          display: !!yAxisLabel,
          text: yAxisLabel,
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 12,
            weight: '600',
          },
          color: DECK_DESIGN_TOKENS.colors.gray[700],
        },
      },
      x: {
        grid: {
          display: false,
        },
        ticks: {
          font: {
            family: DECK_DESIGN_TOKENS.fonts.primary,
            size: 11,
          },
          color: DECK_DESIGN_TOKENS.colors.gray[600],
        },
      },
    },
  };
}

export function getChartDatasetDefaults(colorIndex: number = 0) {
  const colors = DECK_DESIGN_TOKENS.colors.chart;
  const color = colors[colorIndex % colors.length];
  
  return {
    backgroundColor: color,
    borderColor: color,
    borderWidth: 2,
    tension: 0.4, // Smooth curves
  };
}
```

### 3.2 Backend Chart Configuration
**File: `backend/app/services/deck_export_service.py`**
**Location: Modify `_create_chart_config` at line 2533**

```python
def _create_chart_config(self, chart_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create Chart.js configuration with unified styling"""
    if not chart_data:
        return self._create_empty_chart_config()
    
    from app.utils.formatters import DeckFormatter
    
    chart_type = chart_data.get('type', 'bar')
    data = chart_data.get('data', {})
    
    # Validate data
    if not data.get('labels') or not data.get('datasets'):
        logger.warning(f"Chart data missing labels or datasets")
        return self._create_empty_chart_config()
    
    # Calculate max value for Y-axis formatting
    max_value = 0
    for dataset in data.get('datasets', []):
        dataset_max = max(dataset.get('data', [0]))
        max_value = max(max_value, dataset_max)
    
    # Unified color palette
    chart_colors = [
        '#0ea5e9',  # Blue
        '#8b5cf6',  # Purple
        '#10b981',  # Green
        '#f59e0b',  # Orange
        '#ef4444',  # Red
        '#06b6d4',  # Cyan
        '#ec4899',  # Pink
        '#6366f1',  # Indigo
    ]
    
    # Apply colors and styling to datasets
    datasets = data.get('datasets', [])
    for i, dataset in enumerate(datasets):
        color = chart_colors[i % len(chart_colors)]
        dataset['backgroundColor'] = color
        dataset['borderColor'] = color
        dataset['borderWidth'] = 2
        
        if chart_type == 'line':
            dataset['tension'] = 0.4
            dataset['fill'] = False
    
    # Create config with unified options
    config = {
        'type': chart_type,
        'data': data,
        'options': {
            'responsive': True,
            'maintainAspectRatio': False,
            'plugins': {
                'legend': {
                    'position': 'bottom',
                    'labels': {
                        'padding': 16,
                        'font': {
                            'family': "'Inter', sans-serif",
                            'size': 12,
                            'weight': '500'
                        },
                        'color': '#374151',
                        'usePointStyle': True
                    }
                },
                'tooltip': {
                    'backgroundColor': '#111827',
                    'titleFont': {
                        'family': "'Inter', sans-serif",
                        'size': 13,
                        'weight': '600'
                    },
                    'bodyFont': {
                        'family': "'Inter', sans-serif",
                        'size': 12
                    },
                    'padding': 12,
                    'cornerRadius': 6,
                    'callbacks': {
                        'label': f'''function(context) {{
                            const value = context.parsed.y;
                            const formatted = {self._get_js_formatter_function(max_value)};
                            return context.dataset.label + ': ' + formatted(value);
                        }}'''
                    }
                }
            },
            'scales': {
                'y': {
                    'beginAtZero': True,
                    'grid': {
                        'color': '#e5e7eb',
                        'drawBorder': False
                    },
                    'ticks': {
                        'font': {
                            'family': "'Inter', sans-serif",
                            'size': 11
                        },
                        'color': '#6b7280',
                        'callback': f'''function(value) {{
                            {self._get_js_formatter_function(max_value)}
                            return formatter(value);
                        }}'''
                    },
                    'title': {
                        'display': True,
                        'text': chart_data.get('yAxisLabel', 'Value ($M)'),
                        'font': {
                            'family': "'Inter', sans-serif",
                            'size': 12,
                            'weight': '600'
                        },
                        'color': '#374151'
                    }
                },
                'x': {
                    'grid': {
                        'display': False
                    },
                    'ticks': {
                        'font': {
                            'family': "'Inter', sans-serif",
                            'size': 11
                        },
                        'color': '#6b7280'
                    }
                }
            }
        }
    }
    
    return config

def _get_js_formatter_function(self, max_value: float) -> str:
    """Generate JavaScript formatter function"""
    if max_value >= 1_000_000:
        return '''
            function formatter(value) {
                const millions = value / 1000000;
                if (millions >= 1000) {
                    return '$' + (millions / 1000).toFixed(1) + 'B';
                } else {
                    return '$' + millions.toFixed(1) + 'M';
                }
            }
        '''
    elif max_value >= 1000:
        return '''
            function formatter(value) {
                return '$' + (value / 1000).toFixed(0) + 'K';
            }
        '''
    else:
        return '''
            function formatter(value) {
                return '$' + value.toFixed(0);
            }
        '''
```

---

## Part 4: Ensure All Slides Render in Both Web and PDF

### 4.1 Add Slide Rendering Validation
**File: `backend/app/services/deck_export_service.py`**

```python
# ADD at line 1316 in _generate_html_deck:
def _generate_html_deck(self, deck_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
    """Generate professional HTML deck"""
    slides_html = []
    
    if isinstance(deck_data, list):
        slides = deck_data
    else:
        slides = deck_data.get("slides", deck_data.get("deck_slides", []))
    
    logger.info(f"[HTML_DECK] Starting generation for {len(slides)} slides")
    
    # Track which slides render successfully
    successful_slides = []
    failed_slides = []
    
    for slide_idx, slide_data in enumerate(slides):
        slide_type = slide_data.get("type", "unknown")
        slide_title = slide_data.get("content", {}).get("title", f"Slide {slide_idx + 1}")
        
        try:
            # Validate slide has required content
            if not self._validate_slide_for_rendering(slide_data, slide_idx):
                failed_slides.append((slide_idx, slide_type, "Validation failed"))
                continue
            
            slide_html = self._generate_html_slide(slide_data, slide_idx)
            slides_html.append(slide_html)
            successful_slides.append((slide_idx, slide_type))
            logger.info(f"[HTML_DECK] ✓ Slide {slide_idx + 1}/{len(slides)}: {slide_type} - {slide_title}")
            
        except Exception as e:
            logger.error(f"[HTML_DECK] ✗ Slide {slide_idx + 1}/{len(slides)}: {slide_type} - ERROR: {e}")
            failed_slides.append((slide_idx, slide_type, str(e)))
            # Add error placeholder
            slides_html.append(self._html_error_slide(slide_data, slide_idx, str(e)))
    
    # Log summary
    logger.info(f"[HTML_DECK] Rendering complete: {len(successful_slides)} successful, {len(failed_slides)} failed")
    if failed_slides:
        logger.warning(f"[HTML_DECK] Failed slides: {failed_slides}")
    
    # Generate HTML...
```

### 4.2 Increase Chart Wait Time
**File: `backend/app/services/deck_export_service.py`**
**Location: Lines 3096, 3021**

```python
# CHANGE FROM:
page.wait_for_timeout(2000)

# CHANGE TO:
page.wait_for_timeout(10000)  # 10 seconds for all charts to render
await page.evaluate('() => window.chartRenderPromise || Promise.resolve()')
```

### 4.3 Add Chart Rendering Promise
**In the HTML generation, add to the script section:**

```javascript
<script>
    window.chartRenderPromise = new Promise(resolve => {
        let chartsToRender = document.querySelectorAll('canvas[id^="chart-"]').length;
        let chartsRendered = 0;
        
        window.onChartRendered = function() {
            chartsRendered++;
            console.log(`Chart rendered: ${chartsRendered}/${chartsToRender}`);
            if (chartsRendered >= chartsToRender) {
                resolve();
            }
        };
        
        // Timeout fallback
        setTimeout(() => {
            console.log(`Chart render timeout: ${chartsRendered}/${chartsToRender} completed`);
            resolve();
        }, 8000);
    });
    
    document.addEventListener('DOMContentLoaded', function() {
        {self._generate_chart_scripts(deck_data)}
    });
</script>
```

---

## Part 5: Implementation Checklist

### Frontend Changes
- [ ] Create `frontend/src/styles/deck-design-tokens.ts`
- [ ] Create `frontend/src/lib/formatters.ts`
- [ ] Create `frontend/src/lib/chart-config.ts`
- [ ] Update all slide components to use design tokens
- [ ] Update all chart components to use unified config
- [ ] Replace all number displays with formatters

### Backend Changes
- [ ] Create `backend/app/utils/formatters.py`
- [ ] Update `deck_export_service.py` - unified styles
- [ ] Update `deck_export_service.py` - chart config
- [ ] Update `deck_export_service.py` - slide validation
- [ ] Update `deck_export_service.py` - increase wait time
- [ ] Update all deck generation to use formatters

### Testing
- [ ] Generate deck in web view - all 16 slides appear
- [ ] Generate PDF - all 16 slides appear
- [ ] Compare web vs PDF - styles match
- [ ] Check all charts render in web
- [ ] Check all charts render in PDF
- [ ] Verify all $ values show as $XM
- [ ] Verify all Y-axes have proper labels
- [ ] Verify fonts are Inter everywhere
- [ ] Verify colors are consistent
- [ ] No broken charts
- [ ] No missing slides

---

## Quick Implementation Order

1. **Backend formatters** (30 min)
2. **Backend unified styles** (1 hour)
3. **Backend chart config** (1 hour)
4. **Increase wait time & validation** (30 min)
5. **Frontend design tokens** (30 min)
6. **Frontend formatters** (30 min)
7. **Frontend chart config** (1 hour)
8. **Apply to all components** (2-3 hours)
9. **Test both web and PDF** (1 hour)

**Total: ~8-10 hours of focused work**
