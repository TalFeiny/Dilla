"""
Citation Manager for tracking sources and citations in single agent orchestration
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json

class CitationManager:
    """Manages citations and source tracking across tool executions"""
    
    def __init__(self):
        self.citations: List[Dict[str, Any]] = []
        self.source_map: Dict[str, List[int]] = {}  # Map sources to citation indices
        
    def add_citation(self, source: str, date: str, content: str, metadata: Optional[Dict] = None):
        """Add a new citation"""
        citation_id = len(self.citations)
        
        # Create citation hash for deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        citation = {
            'id': citation_id,
            'source': source,
            'date': date,
            'content': content,
            'hash': content_hash,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Check for duplicates
        for existing in self.citations:
            if existing['hash'] == content_hash:
                return existing['id']  # Return existing citation ID
                
        self.citations.append(citation)
        
        # Update source map
        if source not in self.source_map:
            self.source_map[source] = []
        self.source_map[source].append(citation_id)
        
        return citation_id
        
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
            bibliography += f"{citation['id'] + 1}. {citation['source']} ({citation['date']})\n"
            if citation['metadata'].get('title'):
                bibliography += f"   Title: {citation['metadata']['title']}\n"
            bibliography += f"   Content: {citation['content'][:200]}...\n\n"
            
        return bibliography
        
    def merge_citations(self, other_citations: List[Dict]):
        """Merge citations from another source"""
        for citation in other_citations:
            self.add_citation(
                source=citation.get('source', 'Unknown'),
                date=citation.get('date', datetime.now().isoformat()),
                content=citation.get('content', ''),
                metadata=citation.get('metadata', {})
            )
            
    def to_json(self) -> str:
        """Export citations as JSON"""
        return json.dumps({
            'citations': self.citations,
            'source_map': self.source_map
        }, default=str)