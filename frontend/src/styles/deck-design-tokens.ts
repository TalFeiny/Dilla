/**
 * Premium Dual-Mode Design Tokens
 * Sophisticated marble/obsidian light mode and immersive dark mode
 * Professional, depth-rich styling with visual effects
 */

export const DECK_DESIGN_TOKENS = {
  // Typography - Professional, depth-rich hierarchy
  fonts: {
    primary: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    mono: "'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace",
    display: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    body: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  },

  // Neo-Noir Color System - Dark City with Marble/Obsidian Light Mode
  colors: {
    // Legacy compatibility - will be theme-aware
    background: 'hsl(0, 0%, 98%)',        // Clean white (light mode default)
    foreground: 'hsl(0, 0%, 8%)',         // Deep black (light mode default)
    
    primary: {
      DEFAULT: 'hsl(0, 0%, 8%)',          // Deep black
      foreground: 'hsl(0, 0%, 98%)',      // Clean white
    },
    
    secondary: {
      DEFAULT: 'hsl(0, 0%, 95%)',        // Light gray
      foreground: 'hsl(0, 0%, 8%)',       // Deep black
    },
    
    muted: {
      DEFAULT: 'hsl(0, 0%, 90%)',        // Muted gray
      foreground: 'hsl(0, 0%, 45%)',     // Medium gray
    },
    
    border: 'hsl(0, 0%, 88%)',           // Clean borders
    
    // Dual-Mode System - Neo-Noir Dark City + Marble/Obsidian Light
    light: {
      background: {
        primary: '#FFFFFF',      // Pure white
        secondary: '#FAFAFA',    // Marble white
        tertiary: '#F5F5F5',     // Soft marble
      },
      text: {
        primary: '#0A0A0A',      // Obsidian black
        secondary: '#525252',    // Charcoal grey
        tertiary: '#737373',     // Medium grey
        muted: '#A3A3A3',        // Light grey
      },
      border: {
        subtle: '#E5E5E5',       // Light border
        medium: '#D4D4D4',       // Medium border
        strong: '#A3A3A3',       // Strong border
      },
      accent: {
        obsidian: '#0A0A0A',     // Deep obsidian
        grey: '#525252',         // Charcoal accent
      },
      surface: {
        card: '#FFFFFF',         // Card background
        elevated: '#FAFAFA',     // Elevated surface
      }
    },
    
    // Dark Mode - Neo-Noir Dark City Immersive
    dark: {
      background: {
        primary: '#0A0A0F',      // Deep city black
        secondary: '#1A1A24',    // Elevated surface
        tertiary: '#242433',      // Higher elevation
      },
      text: {
        primary: '#FFFFFF',      // Pure white with glow
        secondary: '#E2E8F0',    // Light slate
        tertiary: '#94A3B8',     // Muted slate
        muted: '#64748B',        // Dark slate
      },
      border: {
        subtle: 'rgba(255,255,255,0.06)',   // Subtle glow
        medium: 'rgba(255,255,255,0.12)',    // Medium glow
        strong: 'rgba(255,255,255,0.2)',    // Strong glow
      },
      accent: {
        cyan: '#22D3EE',         // Dark City cyan
        blue: '#3B82F6',         // Electric blue
        green: '#0D4F3C',        // Obsidian green
        glow: 'rgba(34,211,238,0.3)', // Cyan glow
      },
      surface: {
        card: '#1A1A24',         // Elevated card
        elevated: '#242433',     // Higher elevation
        glass: 'rgba(26,26,36,0.8)', // Glassmorphism
      }
    },
    
    // Neo-Noir Chart colors - Dark City aesthetic
    chart: [
      '#0A0A0A',  // Obsidian black
      '#1A1A24',  // Dark city surface
      '#22D3EE',  // Cyan glow
      '#3B82F6',  // Electric blue
      '#0D4F3C',  // Obsidian green
      '#525252',  // Charcoal grey
    ],
    
    // Semantic colors - Theme aware
    success: {
      light: '#059669',
      dark: '#10B981'
    },
    warning: {
      light: '#D97706',
      dark: '#F59E0B'
    },
    error: {
      light: '#DC2626',
      dark: '#EF4444'
    },
    info: {
      light: '#0A0A0A',
      dark: '#22D3EE'
    },
  },

  // Spacing - Surrealist depth and breathing room
  spacing: {
    // Vertical rhythm with surrealist proportions
    hero: '4rem',           // 64px - dramatic presence
    section: '2.5rem',      // 40px - breathing space
    element: '1.5rem',      // 24px - comfortable gaps
    micro: '0.75rem',       // 12px - tight relationships
    
    // Horizontal spacing with golden ratio influence
    container: '2rem',      // 32px - generous margins
    card: '1.5rem',         // 24px - card padding
    input: '1rem',         // 16px - input padding
    button: '0.75rem',      // 12px - button padding
  },

  // Typography Scale - Surrealist hierarchy
  typography: {
    // Hero text - commanding presence
    hero: {
      fontSize: '2.5rem',      // 40px
      fontWeight: 700,
      lineHeight: 1.1,          // Tight for impact
      letterSpacing: '-0.03em', // Condensed for drama
    },
    
    // Display text - floating prominence
    display: {
      fontSize: '2rem',        // 32px
      fontWeight: 600,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    
    // Heading text - clear hierarchy
    heading: {
      fontSize: '1.25rem',      // 20px
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
    },
    
    // Body text - readable flow
    body: {
      fontSize: '0.9375rem',    // 15px
      fontWeight: 400,
      lineHeight: 1.6,          // Generous for readability
    },
    
    // Caption text - subtle presence
    caption: {
      fontSize: '0.8125rem',    // 13px
      fontWeight: 400,
      lineHeight: 1.4,
    },
    
    // Label text - crisp and clear
    label: {
      fontSize: '0.75rem',      // 12px
      fontWeight: 500,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.1em',
    },
    
    // Slide-specific typography
    slideTitle: {
      fontSize: '1.5rem',        // 24px
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    
    slideSubtitle: {
      fontSize: '1rem',          // 16px
      fontWeight: 500,
      lineHeight: 1.4,
      letterSpacing: '-0.01em',
    },
    
    metric: {
      fontSize: '2rem',          // 32px
      fontWeight: 700,
      lineHeight: 1.1,
      letterSpacing: '-0.03em',
    },
  },

  // Shadows - Surrealist depth and atmosphere
  shadows: {
    // Default shadow (light mode)
    subtle: '0 1px 3px rgba(0,0,0,0.06)',
    soft: '0 2px 8px rgba(0,0,0,0.08)',
    medium: '0 4px 16px rgba(0,0,0,0.1)',
    strong: '0 8px 24px rgba(0,0,0,0.12)',
    floating: '0 12px 32px rgba(0,0,0,0.15)',
    
    // Light mode - subtle marble depth
    light: {
      subtle: '0 1px 3px rgba(0,0,0,0.06)',
      soft: '0 2px 8px rgba(0,0,0,0.08)',
      medium: '0 4px 16px rgba(0,0,0,0.1)',
      strong: '0 8px 24px rgba(0,0,0,0.12)',
      floating: '0 12px 32px rgba(0,0,0,0.15)',
    },
    
    // Dark mode - atmospheric glow effects
    dark: {
      subtle: '0 2px 8px rgba(0,0,0,0.3)',
      soft: '0 4px 16px rgba(0,0,0,0.4)',
      medium: '0 8px 24px rgba(0,0,0,0.5)',
      strong: '0 12px 32px rgba(0,0,0,0.6)',
      floating: '0 16px 40px rgba(0,0,0,0.7)',
      
      // Surrealist glow effects
      cyanGlow: '0 0 20px rgba(34,211,238,0.3)',
      blueGlow: '0 0 30px rgba(59,130,246,0.4)',
      innerGlow: 'inset 0 0 20px rgba(34,211,238,0.1)',
      borderGlow: '0 0 0 1px rgba(34,211,238,0.2)',
    },
  },

  // Border Radius - Surrealist organic shapes
  borderRadius: {
    // Default radius values
    small: '0.25rem',       // 4px - precise edges
    medium: '0.5rem',       // 8px - gentle curves
    large: '0.75rem',       // 12px - comfortable
    
    // Sharp, architectural
    sharp: '0.25rem',       // 4px - precise edges
    subtle: '0.5rem',       // 8px - gentle curves
    soft: '0.75rem',        // 12px - comfortable
    organic: '1rem',        // 16px - flowing
    dreamy: '1.5rem',       // 24px - surreal curves
    floating: '2rem',       // 32px - cloud-like
  },

  // Neo-Noir Effects - Dark City atmosphere with surrealist elements
  effects: {
    // Glassmorphism for floating elements
    glass: {
      backdrop: 'blur(12px)',
      background: 'rgba(255,255,255,0.05)',
      border: '1px solid rgba(255,255,255,0.1)',
    },
    
    // Neo-Noir morphing animations
    morph: {
      duration: '300ms',
      easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
      hover: 'scale(1.02)',
      active: 'scale(0.98)',
    },
    
    // Floating animations - dreamlike movement
    float: {
      duration: '2000ms',
      easing: 'ease-in-out',
      distance: '4px',
    },
    
    // Neo-Noir glow effects
    glow: {
      duration: '1500ms',
      easing: 'ease-in-out',
      intensity: '0.3',
      cyan: '0 0 20px rgba(34,211,238,0.3)',
      blue: '0 0 30px rgba(59,130,246,0.4)',
      inner: 'inset 0 0 20px rgba(34,211,238,0.1)',
    },
    
    // Atmospheric perspective - depth illusion
    atmosphere: {
      fadeStart: '0.8',
      fadeEnd: '0.2',
      blurStart: '0px',
      blurEnd: '2px',
    },
    
    // Neo-Noir specific effects
    noir: {
      // Text glow for dark mode
      textGlow: '0 0 20px rgba(255,255,255,0.1)',
      // Border glow
      borderGlow: '0 0 0 1px rgba(34,211,238,0.2)',
      // Inner shadow for depth
      innerShadow: 'inset 0 1px 0 rgba(255,255,255,0.06)',
      // Outer glow for floating elements
      outerGlow: '0 0 40px rgba(34,211,238,0.15)',
    },
  },

  // Neo-Noir Layout - Dark City depth layers
  layout: {
    // Z-index layers for atmospheric depth
    layers: {
      background: -1,      // Deep city background
      surface: 0,          // Base surface level
      elevated: 10,        // Elevated cards
      floating: 20,        // Floating elements
      modal: 30,           // Overlay modals
      overlay: 40,         // Top layer
    },
    
    // Transform origins for Neo-Noir animations
    transforms: {
      center: 'center center',
      top: 'top center',
      bottom: 'bottom center',
      left: 'center left',
      right: 'center right',
    },
  },
} as const;

// Export individual pieces for convenience
export const { fonts, colors, spacing, typography, shadows, borderRadius, effects, layout } = DECK_DESIGN_TOKENS;
