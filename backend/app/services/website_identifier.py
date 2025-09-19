"""
Website Identifier Service
Quickly identifies the correct company website from search results
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
import re

logger = logging.getLogger(__name__)

class WebsiteIdentifier:
    """Quick website identification from search results"""
    
    def __init__(self, claude_client=None):
        self.claude_client = claude_client
    
    async def identify_company_website(
        self, 
        company_name: str, 
        search_results: Dict[str, Any],
        context: Optional[Dict] = None
    ) -> Tuple[str, str, float]:
        """
        Quickly identify the correct company and website from search results
        Returns: (website_url, business_model, confidence)
        """
        company_clean = company_name.replace('@', '').strip()
        
        # PRIORITY 1: If we already extracted websites, just use them!
        if isinstance(context, dict) and context.get('extracted_websites'):
            extracted = context['extracted_websites']
            if extracted and len(extracted) > 0:
                website = extracted[0]
                logger.info(f"[WEBSITE ID] Using pre-extracted website: {website}")
                # Don't hardcode business model - let comprehensive extraction handle it
                return (website, None, 0.9)
        
        # Combine search results into a focused summary
        text_snippets = []
        
        # Add general search results - handle both direct results and nested data.results
        if 'general' in search_results:
            results = search_results['general'].get('results', [])
            if not results and search_results['general'].get('data'):
                results = search_results['general']['data'].get('results', [])
            for result in results[:3]:
                text_snippets.append(f"Title: {result.get('title', '')}\nURL: {result.get('url', '')}\nContent: {result.get('content', '')[:200]}")
        
        # Add funding search results
        if 'funding' in search_results:
            results = search_results['funding'].get('results', [])
            if not results and search_results['funding'].get('data'):
                results = search_results['funding']['data'].get('results', [])
            for result in results[:2]:
                text_snippets.append(f"Funding news: {result.get('title', '')}\nContent: {result.get('content', '')[:200]}")
        
        # Add website search results
        if 'website' in search_results:
            results = search_results['website'].get('results', [])
            if not results and search_results['website'].get('data'):
                results = search_results['website']['data'].get('results', [])
            for result in results[:3]:
                text_snippets.append(f"Website search: {result.get('title', '')}\nURL: {result.get('url', '')}\nContent: {result.get('content', '')[:200]}")
        
        combined_text = "\n\n---\n\n".join(text_snippets)
        
        logger.info(f"Website identifier collected {len(text_snippets)} snippets, total length: {len(combined_text)}")
        
        if not text_snippets or len(combined_text) < 100:
            logger.warning(f"No useful search results found for website identification")
            return ('', None, 0.0)
        
        # Extract any pre-identified websites from context
        extracted_websites = []
        if isinstance(context, dict) and 'extracted_websites' in context:
            extracted_websites = context.get('extracted_websites', [])
            logger.info(f"Using pre-extracted websites: {extracted_websites}")
        
        # Quick identification prompt - much simpler than full extraction
        websites_hint = ""
        if extracted_websites:
            websites_hint = f"\n\nPotential websites found in search snippets: {', '.join(extracted_websites)}"
        
        identification_prompt = f"""Analyze these search results about "{company_clean}" to identify which specific company this is.

{f"User context: {context}" if context and not isinstance(context, dict) else ""}
{f"LinkedIn identifier: {context.get('linkedin_identifier')}" if isinstance(context, dict) and context.get('linkedin_identifier') else ""}
{websites_hint}

Search results:
{combined_text}

Based on these search results, determine:
1. Which specific {company_clean} company this is (there may be multiple companies with this name)
2. Their actual website URL - check the extracted websites list first, validate they match the company profile
3. Their business model based on what they actually do

Return ONLY valid JSON with no other text. Start with {{ and end with }}. 
Example format:
{{
  "company_description": "Brief description identifying which {company_clean} this is",
  "website_url": "the actual company website URL",
  "business_model": "roll-up/saas/marketplace/services/platform",
  "confidence": 0.9,
  "reasoning": "Why you chose this specific {company_clean} and this website"
}}

CRITICAL: Return ONLY the JSON object. No explanations, no markdown, just pure JSON."""

        try:
            if self.claude_client:
                logger.info(f"Using Claude for quick website identification of {company_name}")
                
                import asyncio
                response = await asyncio.wait_for(
                    self.claude_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=500,  # Much smaller response needed
                        temperature=0,
                        messages=[
                            {"role": "user", "content": identification_prompt}
                        ]
                    ),
                    timeout=5.0  # Quick 5 second timeout for identification
                )
                
                import json
                response_text = response.content[0].text if response.content else "{}"
                
                logger.info(f"Raw Claude response for website ID: {response_text[:500]}")
                
                # Clean up response
                response_text = response_text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                
                # Additional cleanup for common Claude response patterns
                response_text = response_text.strip()
                if not response_text:
                    logger.warning("Empty response from Claude for website identification")
                    return self._fallback_identify(search_results, company_clean, context)
                
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing error for {company_clean}: {e}")
                    logger.error(f"Raw response was: {response_text[:200]}...")
                    # Try to extract JSON from the response
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                            logger.info(f"Successfully extracted JSON from response")
                        except:
                            logger.error(f"Failed to extract valid JSON, using fallback")
                            return self._fallback_identify(search_results, company_clean, context)
                    else:
                        return self._fallback_identify(search_results, company_clean, context)
                
                return (
                    result.get('website_url', ''),
                    result.get('business_model', None),  # Don't default to 'saas'
                    result.get('confidence', 0.5)
                )
            else:
                # Fallback to pattern matching
                return self._fallback_identify(search_results, company_clean, context)
                
        except Exception as e:
            logger.error(f"Website identification failed: {e}")
            return self._fallback_identify(search_results, company_clean, context)
    
    def _fallback_identify(self, search_results: Dict, company_name: str, context: Optional[Dict] = None) -> Tuple[str, str, float]:
        """Fallback website identification using patterns"""
        # FIRST: Check if we have pre-extracted websites
        if context and context.get('extracted_websites'):
            extracted = context['extracted_websites']
            if extracted and len(extracted) > 0:
                # Use the first extracted website
                website = extracted[0]
                logger.info(f"[FALLBACK] Using pre-extracted website: {website}")
                return (website, None, 0.8)  # Don't override with generic value
        
        # Look for website patterns in search results
        website_pattern = rf"{company_name.lower()}\.(?:com|io|ai|co|group|app|so)"
        
        for result_type in ['website', 'general', 'funding']:
            if result_type in search_results and search_results[result_type].get('results'):
                for result in search_results[result_type]['results']:
                    # Check URL
                    url = result.get('url', '')
                    if re.search(website_pattern, url, re.IGNORECASE):
                        return (url, None, 0.7)  # Let extraction determine business model
                    
                    # Check content
                    content = result.get('content', '')
                    matches = re.findall(website_pattern, content, re.IGNORECASE)
                    if matches:
                        return (f"https://{matches[0]}", None, 0.6)  # Let extraction determine business model
        
        return ('', None, 0.0)