# Premium Fonts Setup

## Satoshi Fonts (Linear's Premium Font)

To get the premium Linear-level fonts:

1. Download Satoshi Variable fonts from: https://www.onlinewebfonts.com/download/82346df2075cf90ed44a8e36099a87a8
   Or from the official source: https://www.fontshare.com/fonts/satoshi
   
2. Place the following files in this directory:
   - `Satoshi-Variable.woff2` (Variable font - all weights)
   - `Satoshi-VariableItalic.woff2` (Variable italic font)
   - `SatoshiMono-Variable.woff2` (Monospace variable font)

## Alternative: Use CDN (temporary)

If you don't have the font files yet, the system will fallback to Inter which is still premium.

## Font Loading

The fonts are loaded via Next.js font optimization for best performance:
- Automatic font subsetting
- Zero layout shift
- Optimal loading strategy
- Variable font support (300-900 weight range)

## About Satoshi

Satoshi is a premium geometric sans-serif font family created by Indian Type Foundry. It's the same font used by Linear, giving your app that premium Silicon Valley aesthetic.
