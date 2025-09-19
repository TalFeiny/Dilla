"""
Enhanced Citation Manager with numbered clickable citations
Provides inline citation numbers [1] that link to full sources
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import hashlib
import json
import re

class EnhancedCitationManager:
    """
    Enhanced citation manager that provides:
    - Numbered citations [1], [2], etc.
    - Clickable links in formatted output
    - Deduplication of sources
    - Rich metadata tracking
    """
    
    def __init__(self):
        self.citations: List[Dict[str, Any]] = []
        self.source_map: Dict[str, List[int]] = {}  # Map sources to citation indices
        self.url_map: Dict[str, int] = {}  # Map URLs to citation numbers for deduplication
        
    def add_citation(
        self, 
        source: str, 
        date: str, 
        content: str, 
        url: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Tuple[int, str]:
        """
        Add a new citation and return (citation_number, inline_marker)
        
        Returns:
            Tuple of (citation_number, inline_marker like "[1]")
        """
        # Check for duplicate URL
        if url and url in self.url_map:
            citation_num = self.url_map[url]
            return citation_num, f"[{citation_num}]"
        
        # Create citation hash for content deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Check for duplicate content
        for existing in self.citations:
            if existing['hash'] == content_hash:
                return existing['number'], f"[{existing['number']}]"
        
        # Create new citation
        citation_number = len(self.citations) + 1  # 1-based numbering
        
        citation = {
            'id': len(self.citations),
            'number': citation_number,
            'source': source,
            'date': date,
            'title': title or source,
            'content': content,
            'url': url,
            'hash': content_hash,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }
        
        self.citations.append(citation)
        
        # Update maps
        if url:
            self.url_map[url] = citation_number
            
        if source not in self.source_map:
            self.source_map[source] = []
        self.source_map[source].append(citation['id'])
        
        return citation_number, f"[{citation_number}]"
    
    def add_inline_citation(self, text: str, source: str, date: str, url: Optional[str] = None) -> str:
        """
        Add a citation and append the citation number to the text
        
        Example:
            "Revenue grew 50% YoY" -> "Revenue grew 50% YoY [1]"
        """
        citation_num, marker = self.add_citation(
            source=source,
            date=date,
            content=text,
            url=url
        )
        return f"{text} {marker}"
    
    def format_with_citations(self, text: str, citations_data: List[Dict]) -> str:
        """
        Process text with citation placeholders and replace with numbered citations
        
        Input: "Revenue grew 50% {cite:techcrunch,2024} to $100M"
        Output: "Revenue grew 50% [1] to $100M"
        """
        # Pattern to match citation placeholders
        pattern = r'\{cite:([^,]+),([^}]+)\}'
        
        def replace_citation(match):
            source = match.group(1)
            date = match.group(2)
            citation_num, marker = self.add_citation(
                source=source,
                date=date,
                content=f"Reference from {source}",
                url=None
            )
            return marker
        
        return re.sub(pattern, replace_citation, text)
    
    def get_citation_by_number(self, number: int) -> Optional[Dict]:
        """Get a citation by its display number (1-based)"""
        for citation in self.citations:
            if citation['number'] == number:
                return citation
        return None
    
    def format_bibliography_html(self) -> str:
        """
        Format all citations as clickable HTML bibliography
        """
        if not self.citations:
            return "<p>No citations available.</p>"
        
        html = '<div class="citations-bibliography">\n'
        html += '<h3>Sources</h3>\n'
        html += '<ol class="citation-list">\n'
        
        for citation in sorted(self.citations, key=lambda x: x['number']):
            html += f'  <li id="citation-{citation["number"]}" class="citation-item">\n'
            
            # Make title clickable if URL exists
            if citation['url']:
                html += f'    <a href="{citation["url"]}" target="_blank" rel="noopener noreferrer" class="citation-link">\n'
                html += f'      {citation["title"]}\n'
                html += '    </a>\n'
            else:
                html += f'    <span class="citation-title">{citation["title"]}</span>\n'
            
            # Add source and date
            html += f'    <span class="citation-meta">({citation["source"]}, {citation["date"]})</span>\n'
            
            # Add excerpt if available
            if len(citation['content']) > 0:
                excerpt = citation['content'][:200] + ('...' if len(citation['content']) > 200 else '')
                html += f'    <p class="citation-excerpt">{excerpt}</p>\n'
            
            html += '  </li>\n'
        
        html += '</ol>\n'
        html += '</div>\n'
        
        return html
    
    def format_bibliography_markdown(self) -> str:
        """
        Format all citations as markdown with links
        """
        if not self.citations:
            return "No citations available."
        
        md = "## Sources\n\n"
        
        for citation in sorted(self.citations, key=lambda x: x['number']):
            # Format as numbered list with links
            if citation['url']:
                md += f"{citation['number']}. [{citation['title']}]({citation['url']}) "
            else:
                md += f"{citation['number']}. {citation['title']} "
            
            md += f"*({citation['source']}, {citation['date']})*\n"
            
            # Add excerpt
            if len(citation['content']) > 0:
                excerpt = citation['content'][:200] + ('...' if len(citation['content']) > 200 else '')
                md += f"   > {excerpt}\n"
            
            md += "\n"
        
        return md
    
    def get_inline_citations_map(self) -> Dict[str, str]:
        """
        Get a mapping of citation numbers to inline format
        Used for replacing placeholders in text
        """
        return {
            str(c['number']): f"[{c['number']}]"
            for c in self.citations
        }
    
    def process_text_with_citations(self, text: str) -> Tuple[str, List[Dict]]:
        """
        Process text and extract citation opportunities
        Returns processed text with citation markers and list of citations
        """
        # Look for patterns that suggest citations are needed
        patterns = [
            (r'(\d+%)\s+(?:growth|increase|decrease)', 'metric'),
            (r'\$[\d.]+[BMK]?\s+(?:revenue|valuation|funding)', 'financial'),
            (r'(?:according to|per|source:)\s+([^,\n]+)', 'source'),
        ]
        
        processed_text = text
        citations_needed = []
        
        for pattern, citation_type in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                citations_needed.append({
                    'text': match.group(0),
                    'type': citation_type,
                    'position': match.span()
                })
        
        return processed_text, citations_needed
    
    def to_json(self) -> str:
        """Export citations as JSON"""
        return json.dumps({
            'citations': self.citations,
            'source_map': self.source_map,
            'url_map': self.url_map
        }, default=str, indent=2)
    
    def get_citation_stats(self) -> Dict[str, Any]:
        """Get statistics about citations"""
        return {
            'total_citations': len(self.citations),
            'unique_sources': len(self.source_map),
            'unique_urls': len(self.url_map),
            'sources_breakdown': {
                source: len(citations) 
                for source, citations in self.source_map.items()
            }
        }