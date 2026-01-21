"""
Slide Layout Calculator - Ensures all content fits within 1024x768 slide dimensions
"""

from typing import Dict, Any, Optional

# Slide dimension constants
SLIDE_WIDTH = 1024  # pixels
SLIDE_HEIGHT = 768  # pixels
MIN_PADDING = 48  # pixels (3rem)
MAX_PADDING = 64  # pixels (4rem)


class SlideLayoutCalculator:
    """Calculates content constraints to ensure slides fit within 1024x768 boundaries"""
    
    def calculate_text_limits(self, template: str = "default") -> Dict[str, int]:
        """
        Calculate maximum character counts for different text elements.
        
        Returns:
            Dict with max character limits for title, subtitle, body, bullets
        """
        return {
            "title": 60,  # Single line, 2.5rem font
            "subtitle": 120,  # 2 lines max, 1.25rem font
            "body": 500,  # 3 lines max, 1rem font
            "bullet": 80,  # Per bullet
            "max_bullets": 6,  # Maximum number of bullets
            "max_metrics": 8  # Maximum metrics per slide
        }
    
    def calculate_chart_dimensions(
        self, 
        layout_type: str = "full_width",
        has_text_content: bool = False
    ) -> Dict[str, int]:
        """
        Calculate optimal chart dimensions based on layout type.
        
        Args:
            layout_type: "full_width", "half_width", or "side_by_side"
            has_text_content: Whether text content is present on the slide
            
        Returns:
            Dict with width, height, and margin values
        """
        available_width = SLIDE_WIDTH - (MIN_PADDING * 2)
        
        if layout_type == "full_width":
            width = available_width  # 928px
            if has_text_content:
                height = 400  # Leave space for text
            else:
                height = 600  # Can use more space if no text
        elif layout_type == "half_width":
            width = (available_width - 32) // 2  # ~448px with gap
            height = 300
        elif layout_type == "side_by_side":
            width = (available_width - 32) // 2  # ~448px with gap
            height = 400
        else:
            # Default to full width
            width = available_width
            height = 400 if has_text_content else 600
        
        return {
            "width": width,
            "height": height,
            "margin": MIN_PADDING
        }
    
    def validate_slide_fit(self, content: Dict[str, Any]) -> bool:
        """
        Validate that content fits within slide boundaries.
        
        Args:
            content: Slide content dictionary
            
        Returns:
            True if content fits, False otherwise
        """
        limits = self.calculate_text_limits()
        
        # Check title length
        if content.get("title"):
            if len(str(content["title"])) > limits["title"]:
                return False
        
        # Check subtitle length
        if content.get("subtitle"):
            if len(str(content["subtitle"])) > limits["subtitle"]:
                return False
        
        # Check body length
        if content.get("body"):
            if len(str(content["body"])) > limits["body"]:
                return False
        
        # Check bullets
        if content.get("bullets"):
            bullets = content["bullets"]
            if isinstance(bullets, list):
                if len(bullets) > limits["max_bullets"]:
                    return False
                for bullet in bullets:
                    if len(str(bullet)) > limits["bullet"]:
                        return False
        
        # Check metrics count
        if content.get("metrics"):
            metrics = content["metrics"]
            if isinstance(metrics, list) and len(metrics) > limits["max_metrics"]:
                return False
        
        return True
    
    def calculate_spacing(self, content_type: str = "default") -> Dict[str, int]:
        """
        Calculate padding and margins based on content type.
        
        Returns:
            Dict with padding values
        """
        return {
            "padding": MIN_PADDING,
            "margin": MIN_PADDING,
            "gap": 16  # Gap between elements
        }

