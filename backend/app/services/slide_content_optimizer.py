"""
Slide Content Optimizer - Optimizes content to fit within slide size limits
"""

import re
from typing import Dict, Any, List, Optional


class SlideContentOptimizer:
    """Optimizes generated content to fit within calculated limits"""
    
    def optimize_text_content(
        self, 
        content: Dict[str, Any], 
        constraints: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Optimize text content to fit within constraints.
        
        Args:
            content: Original content dictionary
            constraints: Constraints from SlideLayoutCalculator
            
        Returns:
            Optimized content dictionary
        """
        optimized = content.copy()
        
        # REMOVED: Title and subtitle truncation - let frontend handle overflow with CSS
        # Titles and subtitles are no longer truncated to preserve full information
        # Frontend CSS should handle overflow with responsive font sizing
        
        # Optimize body
        # REMOVED: Hard truncation - let frontend handle overflow with CSS
        # Body text is no longer truncated at content level to preserve full information
        if "body" in optimized and optimized["body"]:
            # Only strip markdown and format, but don't truncate
            optimized["body"] = self.strip_markdown(str(optimized["body"]))
        
        # Optimize bullets
        if "bullets" in optimized and optimized["bullets"]:
            optimized["bullets"] = self.optimize_bullets(
                optimized["bullets"],
                constraints
            )
        
        # Optimize metrics
        if "metrics" in optimized and optimized["metrics"]:
            optimized["metrics"] = self.optimize_metrics(
                optimized["metrics"],
                constraints.get("max_metrics", 8)
            )
        
        return optimized
    
    def optimize_bullets(
        self, 
        bullets: List[Any], 
        constraints: Dict[str, int]
    ) -> List[str]:
        """
        Optimize bullet list to fit within constraints.
        
        Args:
            bullets: List of bullet items
            constraints: Constraints dictionary
            
        Returns:
            Optimized list of bullet strings
        """
        # REMOVED: Bullet truncation limits - preserve all bullets and full text
        # Frontend CSS should handle overflow with responsive layouts
        # Only remove markdown formatting, don't truncate content
        optimized = []
        for bullet in bullets:
            bullet_str = str(bullet)
            # Remove markdown if present, but preserve full content
            bullet_str = self.strip_markdown(bullet_str)
            optimized.append(bullet_str)
        
        return optimized
    
    def optimize_metrics(
        self, 
        metrics: List[Any], 
        max_count: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Select most important metrics if count exceeds limit.
        
        Args:
            metrics: List of metric dictionaries
            max_count: Maximum number of metrics
            
        Returns:
            Optimized list of metrics
        """
        if not isinstance(metrics, list):
            return []
        
        # If within limit, just return as-is
        if len(metrics) <= max_count:
            return metrics
        
        # Otherwise, take first max_count (assuming they're ordered by importance)
        return metrics[:max_count]
    
    def strip_markdown(self, text: str) -> str:
        """
        Remove markdown syntax, JSON dumps, AI-generated artifacts, and emojis from text.
        
        Args:
            text: Text that may contain markdown or AI artifacts
            
        Returns:
            Clean text without markdown or AI artifacts
        """
        if not isinstance(text, str):
            return str(text)
        
        # Remove emojis and non-text characters (keep only alphanumeric, spaces, punctuation)
        # This removes all Unicode emoji characters and other non-standard characters
        text = re.sub(r'[^\w\s\.,;:!?\-\(\)\[\]\/\@\#\$\%\&\*\+\=\<\>\|\{\}\'\"\\]', '', text)
        
        # Remove JSON dumps and Python dict representations more aggressively
        # Pattern: {'key': 'value'} or {"key": "value"} or {key: value}
        text = re.sub(r"\{[^{}]*['\"]?\w+['\"]?\s*:\s*[^{}]*\}", '', text)
        text = re.sub(r"\{[^{}]*\}", '', text)  # Any remaining dict-like structures
        
        # Remove JSON.stringify patterns
        text = re.sub(r'JSON\.stringify\([^)]+\)', '', text, flags=re.IGNORECASE)
        
        # Remove filler code patterns
        text = re.sub(r'```[\s\S]*?```', '', text)  # Code blocks
        text = re.sub(r'`[^`]+`', '', text)  # Inline code
        text = re.sub(r'<[^>]+>', '', text)  # HTML tags
        
        # Remove filler code keywords
        text = re.sub(r'\b(filler|placeholder|dummy|test|example\.com|lorem|ipsum)\b', '', text, flags=re.IGNORECASE)
        
        # Remove AI-generated phrases
        ai_phrases = [
            r'Here is|Here\'s|Here are',
            r'Based on|According to|As per',
            r'Note that|Please note|It should be noted',
            r'In summary|To summarize|In conclusion',
            r'This shows|This indicates|This suggests',
            r'It is important to|It should be|It must be',
            r'Let me|Allow me|I will|I can',
        ]
        for phrase in ai_phrases:
            text = re.sub(phrase, '', text, flags=re.IGNORECASE)
        
        # Remove markdown syntax
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)  # *italic*
        text = re.sub(r'__([^_]+)__', r'\1', text)  # __bold__
        text = re.sub(r'_([^_]+)_', r'\1', text)  # _italic_
        
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        
        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove excessive whitespace and newlines
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
        text = re.sub(r' {3,}', ' ', text)  # Max 2 spaces
        
        # Remove common AI filler words at start
        text = re.sub(r'^(The|A|An)\s+', '', text, flags=re.IGNORECASE)
        
        # Remove any remaining JSON-like structures at start/end
        text = re.sub(r'^\s*[\{\[]', '', text)  # Remove leading { or [
        text = re.sub(r'[\}\]]\s*$', '', text)  # Remove trailing } or ]
        
        return text.strip()
    
    def format_for_slide(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply professional formatting to content and remove AI artifacts.
        
        Args:
            content: Content dictionary
            
        Returns:
            Formatted content
        """
        formatted = content.copy()
        
        # Strip markdown and AI artifacts from all text fields
        for field in ["title", "subtitle", "body", "description", "summary", "insights", "notes"]:
            if field in formatted and formatted[field]:
                cleaned = self.strip_markdown(str(formatted[field]))
                # Remove any remaining dict/list string representations
                if cleaned.strip().startswith(('{', '[')):
                    cleaned = self._extract_text_from_structure(cleaned)
                formatted[field] = cleaned
        
        # Clean bullets too
        if "bullets" in formatted and isinstance(formatted["bullets"], list):
            formatted["bullets"] = [
                self.strip_markdown(str(b)) if isinstance(b, str) else str(b)
                for b in formatted["bullets"]
            ]
        
        # Format numbers (e.g., $5M instead of $5,000,000)
        for field in ["body", "description", "summary"]:
            if field in formatted and formatted[field]:
                formatted[field] = self._format_numbers(str(formatted[field]))
        
        return formatted
    
    def _extract_text_from_structure(self, text: str) -> str:
        """Extract readable text from JSON/dict string representations"""
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Extract values, skip keys that look like metadata
                values = [str(v) for k, v in parsed.items() 
                        if not k.startswith('_') and v not in [None, '', []]]
                return ' '.join(values)
            elif isinstance(parsed, list):
                return ' '.join(str(v) for v in parsed if v not in [None, '', []])
        except:
            pass
        # If parsing fails, try to extract quoted strings
        matches = re.findall(r'["\']([^"\']+)["\']', text)
        if matches:
            return ' '.join(matches)
        return text
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max length, preserving words when possible"""
        if len(text) <= max_length:
            return text
        
        # Try to truncate at word boundary
        truncated = text[:max_length - 3]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.7:  # If space is reasonably close
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    def _format_numbers(self, text: str) -> str:
        """Format large numbers to abbreviated form (e.g., $5M)"""
        # This is a simple version - could be enhanced
        # Pattern: $5,000,000 -> $5M
        def replace_number(match):
            num_str = match.group(1).replace(',', '')
            try:
                num = float(num_str)
                if num >= 1_000_000_000:
                    return f"${num/1_000_000_000:.1f}B"
                elif num >= 1_000_000:
                    return f"${num/1_000_000:.1f}M"
                elif num >= 1_000:
                    return f"${num/1_000:.1f}K"
            except ValueError:
                pass
            return match.group(0)
        
        # Match dollar amounts with commas
        text = re.sub(r'\$([\d,]+)', replace_number, text)
        return text

