"""
Chart Sizing Service - Calculates optimal chart dimensions for slides
"""

from typing import Dict, Any, Optional


class ChartSizingService:
    """Calculates optimal chart dimensions based on slide layout and content"""
    
    def calculate_chart_size(
        self,
        layout_type: str = "full_width",
        has_text_content: bool = False,
        has_metrics: bool = False
    ) -> Dict[str, int]:
        """
        Calculate optimal chart dimensions.
        
        Args:
            layout_type: "full_width", "half_width", or "side_by_side"
            has_text_content: Whether text content is present
            has_metrics: Whether metrics are present
            
        Returns:
            Dict with width, height, and margin values
        """
        SLIDE_WIDTH = 1024
        SLIDE_HEIGHT = 768
        PADDING = 48
        
        available_width = SLIDE_WIDTH - (PADDING * 2)  # 928px
        
        if layout_type == "full_width":
            width = available_width
            if has_metrics:
                height = 350  # Leave space for metrics grid
            elif has_text_content:
                height = 400  # Leave space for text
            else:
                height = 600  # Standalone chart can be taller
        elif layout_type == "half_width":
            width = (available_width - 32) // 2  # ~448px with gap
            height = 300
        elif layout_type == "side_by_side":
            width = (available_width - 32) // 2  # ~448px with gap
            height = 400
        else:
            # Default
            width = available_width
            height = 400 if has_text_content else 600
        
        return {
            "width": width,
            "height": height,
            "margin": PADDING
        }
    
    def adjust_for_content(
        self,
        chart_dimensions: Dict[str, int],
        content_type: str = "text"
    ) -> Dict[str, int]:
        """
        Adjust chart size if text content is present.
        
        Args:
            chart_dimensions: Current chart dimensions
            content_type: Type of content ("text", "metrics", "both", "none")
            
        Returns:
            Adjusted dimensions
        """
        adjusted = chart_dimensions.copy()
        
        if content_type == "text":
            adjusted["height"] = min(adjusted["height"], 400)
        elif content_type == "metrics":
            adjusted["height"] = min(adjusted["height"], 350)
        elif content_type == "both":
            adjusted["height"] = min(adjusted["height"], 300)
        
        return adjusted
    
    def validate_chart_fit(
        self,
        chart_dimensions: Dict[str, int],
        slide_width: int = 1024,
        slide_height: int = 768
    ) -> bool:
        """
        Validate that chart fits within slide boundaries.
        
        Args:
            chart_dimensions: Chart dimensions dict
            slide_width: Slide width in pixels
            slide_height: Slide height in pixels
            
        Returns:
            True if chart fits, False otherwise
        """
        width = chart_dimensions.get("width", 0)
        height = chart_dimensions.get("height", 0)
        margin = chart_dimensions.get("margin", 48)
        
        # Check width
        if width + (margin * 2) > slide_width:
            return False
        
        # Check height (accounting for title space ~100px)
        if height + margin + 100 > slide_height:
            return False
        
        return True
    
    def get_chart_margins(self, layout_type: str = "full_width") -> Dict[str, int]:
        """
        Calculate proper margins for chart container.
        
        Returns:
            Dict with margin values
        """
        return {
            "top": 100,  # Space for title
            "bottom": 48,
            "left": 48,
            "right": 48
        }

