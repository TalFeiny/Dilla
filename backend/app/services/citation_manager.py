"""
Citation Manager for tracking sources and citations in single agent orchestration
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json
import asyncio

class CitationManager:
    """Manages citations and source tracking across tool executions"""
    
    def __init__(self):
        self.citations: List[Dict[str, Any]] = []
        self.source_map: Dict[str, List[int]] = {}  # Map sources to citation indices
        self.url_set: set = set()  # Track unique URLs to prevent duplicates
        self.citation_counter = 1  # Start numbering from [1]
        self._lock = asyncio.Lock()  # Thread safety for parallel operations
        
    def add_citation(self, source: str, date: str, content: str, metadata: Optional[Dict] = None, url: Optional[str] = None, title: Optional[str] = None):
        """Add a new citation with URL and title support"""
        # Use URL for deduplication if provided, otherwise use source
        dedup_key = url if url else source
        
        if dedup_key in self.url_set:
            # Find and return existing citation ID
            for existing in self.citations:
                if existing.get('url') == url or existing['source'] == source:
                    return existing['citation_number']
            return len(self.citations)  # Fallback
        
        citation_number = self.citation_counter
        self.citation_counter += 1
        
        # Create citation hash for additional deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        citation = {
            'citation_number': citation_number,  # Human-readable number [1], [2], etc.
            'source': source,
            'url': url or source,  # Use source as URL if no URL provided
            'title': title or source,  # Use source as title if no title provided
            'date': date,
            'content': content,
            'hash': content_hash,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }
        
        self.citations.append(citation)
        self.url_set.add(dedup_key)  # Track the deduplication key
        
        # Update source map
        if source not in self.source_map:
            self.source_map[source] = []
        self.source_map[source].append(citation_number)
        
        return citation_number
        
    def get_citation(self, citation_id: int) -> Optional[Dict]:
        """Get a specific citation by ID"""
        if 0 <= citation_id < len(self.citations):
            return self.citations[citation_id]
        return None
        
    def get_citations_by_source(self, source: str) -> List[Dict]:
        """Get all citations from a specific source"""
        citation_ids = self.source_map.get(source, [])
        return [self.citations[cid] for cid in citation_ids]
        
    def get_all_citations(self) -> List[Dict]:
        """Get all citations"""
        return self.citations
        
    def format_citation(self, citation_id: int) -> str:
        """Format a citation for inline use"""
        citation = self.get_citation(citation_id)
        if citation:
            return f"[Source: {citation['source']}, Date: {citation['date']}]"
        return "[Citation not found]"
        
    def format_all_citations(self) -> str:
        """Format all citations as a bibliography"""
        if not self.citations:
            return "No citations available."
            
        bibliography = "## Sources\n\n"
        for citation in self.citations:
            citation_num = citation.get('citation_number', citation.get('id', 0) + 1)
            title = citation.get('title', citation['source'])
            url = citation.get('url', citation['source'])
            bibliography += f"{citation_num}. {title} ({citation['date']})\n"
            if citation['metadata'].get('title'):
                bibliography += f"   Title: {citation['metadata']['title']}\n"
            bibliography += f"   Content: {citation['content'][:200]}...\n\n"
            
        return bibliography
    
    def get_citations_html(self) -> str:
        """Return formatted HTML with clickable links"""
        if not self.citations:
            return ""
            
        html = '<div class="sources"><h4>Sources</h4>\n'
        for citation in self.citations:
            citation_num = citation.get('citation_number', citation.get('id', 0) + 1)
            title = citation.get('title', citation['source'])
            url = citation.get('url', citation['source'])
            
            # Only make it clickable if it's a real URL
            if url.startswith('http'):
                link_html = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            else:
                link_html = title
                
            html += f'<div>[{citation_num}] {link_html}</div>\n'
        html += '</div>'
        
        return html
    
    def get_citations_for_slide(self, slide_id: str) -> List[Dict]:
        """Return citations used in this slide (placeholder for slide-specific citations)"""
        # For now, return all citations. In the future, we could track per-slide citations
        return self.citations
    
    def get_citation_by_number(self, citation_number: int) -> Optional[Dict]:
        """Get a specific citation by its human-readable number"""
        for citation in self.citations:
            if citation.get('citation_number') == citation_number:
                return citation
        return None
        
    def merge_citations(self, other_citations: List[Dict], deduplicate: bool = True):
        """Merge citations from another source with thread-safe deduplication"""
        for citation in other_citations:
            # Check for duplicates if deduplication is enabled
            if deduplicate:
                url = citation.get('url') or citation.get('source')
                if url and url in self.url_set:
                    continue  # Skip duplicate
                content = citation.get('content', '')
                if content:
                    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
                    # Check if we already have this content
                    if any(c.get('hash') == content_hash for c in self.citations):
                        continue  # Skip duplicate content
            
            self.add_citation(
                source=citation.get('source', 'Unknown'),
                date=citation.get('date', datetime.now().isoformat()),
                content=citation.get('content', ''),
                metadata=citation.get('metadata', {}),
                url=citation.get('url'),
                title=citation.get('title')
            )
            
    def to_json(self) -> str:
        """Export citations as JSON"""
        return json.dumps({
            'citations': self.citations,
            'source_map': self.source_map
        }, default=str)