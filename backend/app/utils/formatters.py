"""
Unified formatting utilities for deck generation
Ensures consistent number formatting across web and PDF outputs
"""

class DeckFormatter:
    """Format values consistently across deck"""
    
    @staticmethod
    def format_currency(value: float) -> str:
        """
        Format currency values in millions (no decimals unless < $1M)
        Examples: $5M, $150M, $2B, $500K
        """
        # Defensive: handle None, 0, and invalid values
        if value is None:
            return "$0"
        
        # Handle string input
        if isinstance(value, str):
            try:
                value = float(value)
            except (ValueError, TypeError):
                return "$0"
        
        # Handle invalid numbers
        if not isinstance(value, (int, float)) or value != value:  # NaN check
            return "$0"
            
        if value == 0:
            return "$0"
        
        millions = value / 1_000_000
        
        if millions >= 1000:
            # Billions - no decimal
            billions = millions / 1000
            if billions >= 10:
                return f"${billions:.0f}B"
            else:
                return f"${billions:.1f}B"
        elif millions >= 1:
            # Millions - no decimal for whole numbers
            if millions >= 10:
                return f"${millions:.0f}M"
            else:
                # Show decimal for < $10M
                return f"${millions:.1f}M" if millions % 1 != 0 else f"${millions:.0f}M"
        elif millions >= 0.01:
            # Hundreds of thousands - show as decimal M
            return f"${millions:.1f}M"
        else:
            # Thousands
            thousands = value / 1000
            return f"${thousands:.0f}K"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Format percentages
        Examples: 15.6%, 2.1%, 150%
        """
        if value is None:
            return "N/A"
        
        # Handle both decimal (0.156) and percentage (15.6) inputs
        if abs(value) <= 1:
            percentage = value * 100
        else:
            percentage = value
        
        return f"{percentage:.{decimals}f}%"
    
    @staticmethod
    def format_multiple(value: float, decimals: int = 1) -> str:
        """
        Format multiples
        Examples: 12.5x, 2.1x
        """
        if value is None:
            return "N/A"
        return f"{value:.{decimals}f}x"
    
    @staticmethod
    def format_chart_axis_value(value: float, max_value: float) -> str:
        """Format axis values based on scale (for Y-axis ticks)"""
        if max_value >= 1_000_000:
            return DeckFormatter.format_currency(value)
        elif max_value >= 1000:
            return f"${value/1000:.0f}K"
        else:
            return f"${value:.0f}"
    
    @staticmethod
    def get_axis_label_for_currency() -> str:
        """Get standardized Y-axis label for currency charts"""
        return "Value"
