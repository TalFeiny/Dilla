#!/usr/bin/env python3
"""
Simple M&A deal extractor for PWERM analysis
Focuses on extracting: Acquirer, Target Company, Deal Value from Tavily search results
"""

import json
import sys
import os
import requests
import re
from typing import Dict, List, Optional, Tuple

class MADealExtractor:
    def __init__(self, tavily_api_key: str = None):
        """Initialize M&A Deal Extractor with Tavily API"""
        self.tavily_api_key = tavily_api_key or os.getenv('TAVILY_API_KEY')
        self.tavily_base_url = "https://api.tavily.com/search"
    
    def search_sector_deals(self, sector: str, subsector: str = None) -> Dict:
        """Search for M&A deals in a specific sector"""
        deals = {
            "ma_transactions": [],
            "raw_results": []
        }
        
        if not self.tavily_api_key:
            sys.stderr.write("No Tavily API key found\n")
            return deals
        
        # Construct targeted M&A search queries
        search_queries = []
        
        if subsector:
            full_sector = f"{sector} {subsector}"
            search_queries.extend([
                f'"{subsector}" companies "acquired" "for $" million billion acquirer',
                f'"{subsector}" "acquisition" "deal value" "bought by" price',
                f'"{subsector}" M&A deals "sold to" valuation amount',
                f'"{full_sector}" acquisitions "purchase price" buyer seller'
            ])
        else:
            search_queries.extend([
                f'"{sector}" companies "acquired" "for $" million billion acquirer',
                f'"{sector}" "acquisition" "deal value" "bought by" price',
                f'"{sector}" M&A deals "sold to" valuation amount',
                f'"{sector}" acquisitions "purchase price" buyer seller'
            ])
        
        # Add year-specific searches for recent deals
        search_queries.extend([
            f'"{sector}" acquisitions 2024 "million" "billion" price',
            f'"{sector}" M&A 2025 "acquired for" valuation'
        ])
        
        all_deals = []
        seen_deals = set()  # Track unique deals by (acquirer, target) tuple
        
        for query in search_queries[:4]:  # Limit to avoid too many API calls
            sys.stderr.write(f"Searching: {query}\n")
            
            try:
                response = requests.post(
                    self.tavily_base_url,
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": 20,
                        "include_answer": True
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deals["raw_results"].extend(data.get('results', []))
                    
                    # Extract deals from the answer if available
                    if data.get('answer'):
                        answer_deals = self._extract_deals_from_text(data['answer'], sector)
                        for deal in answer_deals:
                            deal_key = (deal.get('acquirer', ''), deal.get('target', ''))
                            if deal_key not in seen_deals and deal_key[0] and deal_key[1]:
                                seen_deals.add(deal_key)
                                all_deals.append(deal)
                    
                    # Extract deals from each search result
                    for result in data.get('results', []):
                        content = result.get('content', '')
                        title = result.get('title', '')
                        url = result.get('url', '')
                        
                        # Extract deals from content
                        content_deals = self._extract_deals_from_text(
                            content + ' ' + title, 
                            sector,
                            source_url=url
                        )
                        
                        for deal in content_deals:
                            deal_key = (deal.get('acquirer', ''), deal.get('target', ''))
                            if deal_key not in seen_deals and deal_key[0] and deal_key[1]:
                                seen_deals.add(deal_key)
                                all_deals.append(deal)
                
            except Exception as e:
                sys.stderr.write(f"Error searching Tavily: {e}\n")
        
        # Sort deals by value (highest first)
        all_deals.sort(key=lambda x: x.get('deal_value_millions', 0), reverse=True)
        deals["ma_transactions"] = all_deals[:20]  # Return top 20 deals
        
        sys.stderr.write(f"Found {len(all_deals)} unique M&A deals in {sector}\n")
        return deals
    
    def _extract_deals_from_text(self, text: str, sector: str, source_url: str = "") -> List[Dict]:
        """Extract M&A deals from text using multiple patterns"""
        deals = []
        
        # Pattern 1: "X acquired/bought Y for $Z"
        patterns = [
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:acquired|bought|acquires|buys|purchased)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+for\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:acquired|bought|acquires|buys)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)[^.]*?\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:to acquire|acquiring|will acquire)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+for\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
            # Pattern for "Y sold to X for $Z"
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:sold to|sells to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+for\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
            # Pattern for deal value mentioned separately
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:acquisition of|acquires?|bought)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)[^.]{0,50}(?:deal|transaction|purchase|valuation)[^.]{0,30}\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match) >= 3:
                    # Handle different match formats
                    if 'sold to' in pattern:
                        target, acquirer, value_str = match[0], match[1], match[2]
                    else:
                        acquirer, target, value_str = match[0], match[1], match[2]
                    
                    # Clean up company names
                    acquirer = self._clean_company_name(acquirer)
                    target = self._clean_company_name(target)
                    
                    # Skip if names are too short or generic
                    if len(acquirer) < 3 or len(target) < 3:
                        continue
                    if acquirer.lower() in ['the', 'and', 'for', 'with', 'from']:
                        continue
                    if target.lower() in ['the', 'and', 'for', 'with', 'from']:
                        continue
                    
                    # Parse value
                    value_millions = self._parse_value_to_millions(value_str, text)
                    
                    if value_millions > 0:
                        # Extract year if possible
                        year = self._extract_year(text, acquirer, target)
                        
                        deals.append({
                            "acquirer": acquirer,
                            "target": target,
                            "deal_value_millions": value_millions,
                            "deal_value_formatted": self._format_value(value_millions),
                            "year": year,
                            "sector": sector,
                            "source": source_url if source_url else "Tavily Search",
                            "confidence": "high" if all([acquirer, target, value_millions]) else "medium"
                        })
        
        # Also look for lists of deals in structured format
        list_pattern = r'•\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)[:\s]+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)[^•]*?\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)'
        list_matches = re.findall(list_pattern, text, re.IGNORECASE)
        for match in list_matches:
            acquirer, target, value_str = match
            acquirer = self._clean_company_name(acquirer)
            target = self._clean_company_name(target)
            value_millions = self._parse_value_to_millions(value_str, text)
            
            if value_millions > 0 and len(acquirer) > 2 and len(target) > 2:
                year = self._extract_year(text, acquirer, target)
                deals.append({
                    "acquirer": acquirer,
                    "target": target,
                    "deal_value_millions": value_millions,
                    "deal_value_formatted": self._format_value(value_millions),
                    "year": year,
                    "sector": sector,
                    "source": source_url if source_url else "Tavily Search",
                    "confidence": "medium"
                })
        
        return deals
    
    def _clean_company_name(self, name: str) -> str:
        """Clean up company name"""
        # Remove common suffixes
        name = re.sub(r'\s+(Inc\.?|Corp\.?|LLC|Ltd\.?|Limited|Company|Co\.?)$', '', name, flags=re.IGNORECASE)
        # Remove extra spaces
        name = ' '.join(name.split())
        return name.strip()
    
    def _parse_value_to_millions(self, value_str: str, context: str = "") -> float:
        """Parse value string to millions"""
        try:
            # Remove commas and $ sign
            value_str = value_str.replace(',', '').replace('$', '').strip()
            value = float(value_str)
            
            # Check if it's in billions
            if 'billion' in context.lower() or 'B' in context:
                value *= 1000  # Convert to millions
            
            return value
        except:
            return 0
    
    def _format_value(self, millions: float) -> str:
        """Format value for display"""
        if millions >= 1000:
            return f"${millions/1000:.1f}B"
        else:
            return f"${millions:.0f}M"
    
    def _extract_year(self, text: str, acquirer: str = "", target: str = "") -> Optional[str]:
        """Extract year from text near the deal mention"""
        # Look for year near the company names
        search_area = text
        if acquirer and target:
            # Find the deal mention and look around it
            deal_pattern = f"{acquirer}.*?{target}"
            match = re.search(deal_pattern, text, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                search_area = text[start:end]
        
        # Look for years 2020-2025
        year_pattern = r'\b(202[0-5])\b'
        year_match = re.search(year_pattern, search_area)
        if year_match:
            return year_match.group(1)
        
        # Default to recent if no year found
        return "2024"


def main():
    """Main function for testing"""
    # Get API key
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        print("Error: TAVILY_API_KEY not found in environment")
        return
    
    # Test with HR Tech sector
    extractor = MADealExtractor(tavily_key)
    
    # Search for deals
    sector = "SaaS"
    subsector = "HR Tech"
    
    print(f"Searching for M&A deals in {sector} - {subsector}...")
    results = extractor.search_sector_deals(sector, subsector)
    
    # Display results
    print(f"\nFound {len(results['ma_transactions'])} M&A deals:\n")
    
    for i, deal in enumerate(results['ma_transactions'][:10], 1):
        print(f"{i}. {deal['acquirer']} acquired {deal['target']}")
        print(f"   Deal Value: {deal['deal_value_formatted']}")
        print(f"   Year: {deal['year']}")
        print(f"   Confidence: {deal['confidence']}")
        print()


if __name__ == "__main__":
    main()