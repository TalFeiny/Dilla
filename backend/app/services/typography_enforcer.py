"""
Typography Enforcer - Ensures consistent typography hierarchy across slides
"""

from typing import Dict, Any, Optional


class TypographyEnforcer:
    """Enforces consistent typography hierarchy matching frontend design tokens"""
    
    # Typography constants matching frontend design tokens
    TITLE_FONT_SIZE = "2.5rem"
    TITLE_FONT_WEIGHT = 700
    TITLE_LINE_HEIGHT = 1.1
    TITLE_LETTER_SPACING = "-0.03em"
    
    SUBTITLE_FONT_SIZE = "1.25rem"
    SUBTITLE_FONT_WEIGHT = 500
    SUBTITLE_LINE_HEIGHT = 1.4
    
    BODY_FONT_SIZE = "0.9375rem"  # 15px
    BODY_FONT_WEIGHT = 400
    BODY_LINE_HEIGHT = 1.6
    
    METRIC_FONT_SIZE = "2rem"
    METRIC_FONT_WEIGHT = 700
    
    def enforce_title_style(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure title follows design tokens"""
        if "title" in content and content["title"]:
            # Title should be max 60 chars, single line
            title = str(content["title"])
            if len(title) > 60:
                content["title"] = title[:57] + "..."
        
        return content
    
    def enforce_subtitle_style(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure subtitle follows design tokens"""
        if "subtitle" in content and content["subtitle"]:
            # Subtitle should be max 120 chars, 2 lines max
            subtitle = str(content["subtitle"])
            if len(subtitle) > 120:
                content["subtitle"] = subtitle[:117] + "..."
        
        return content
    
    def enforce_body_style(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure body text follows design tokens"""
        if "body" in content and content["body"]:
            # Body should be max 500 chars, 3 lines max
            body = str(content["body"])
            if len(body) > 500:
                content["body"] = body[:497] + "..."
        
        return content
    
    def calculate_font_sizes(self, content_density: str = "normal") -> Dict[str, str]:
        """
        Calculate font sizes based on content density.
        
        Args:
            content_density: "low", "normal", or "high"
            
        Returns:
            Dict with font size values
        """
        # For now, return standard sizes
        # Could adjust based on density if needed
        return {
            "title": self.TITLE_FONT_SIZE,
            "subtitle": self.SUBTITLE_FONT_SIZE,
            "body": self.BODY_FONT_SIZE,
            "metric": self.METRIC_FONT_SIZE
        }
    
    def validate_typography(self, content: Dict[str, Any]) -> bool:
        """
        Check that all text follows typography hierarchy rules.
        
        Args:
            content: Content dictionary
            
        Returns:
            True if typography is valid
        """
        # Check title length
        if "title" in content and content["title"]:
            if len(str(content["title"])) > 60:
                return False
        
        # Check subtitle length
        if "subtitle" in content and content["subtitle"]:
            if len(str(content["subtitle"])) > 120:
                return False
        
        # Check body length
        if "body" in content and content["body"]:
            if len(str(content["body"])) > 500:
                return False
        
        return True
    
    def get_typography_metadata(self) -> Dict[str, Any]:
        """
        Get typography constants for frontend rendering.
        
        Returns:
            Dict with typography values
        """
        return {
            "title": {
                "fontSize": self.TITLE_FONT_SIZE,
                "fontWeight": self.TITLE_FONT_WEIGHT,
                "lineHeight": self.TITLE_LINE_HEIGHT,
                "letterSpacing": self.TITLE_LETTER_SPACING
            },
            "subtitle": {
                "fontSize": self.SUBTITLE_FONT_SIZE,
                "fontWeight": self.SUBTITLE_FONT_WEIGHT,
                "lineHeight": self.SUBTITLE_LINE_HEIGHT
            },
            "body": {
                "fontSize": self.BODY_FONT_SIZE,
                "fontWeight": self.BODY_FONT_WEIGHT,
                "lineHeight": self.BODY_LINE_HEIGHT
            },
            "metric": {
                "fontSize": self.METRIC_FONT_SIZE,
                "fontWeight": self.METRIC_FONT_WEIGHT
            }
        }

