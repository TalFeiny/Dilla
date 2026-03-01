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
    
    def __init__(self, model_router=None):
        self.model_router = model_router
    
    def _ensure_string(self, value: Any, default: str = "") -> str:
        """Convert any value to a string safely"""
        if value is None:
            return default
        if isinstance(value, dict):
            # Try common dict fields that might contain the actual string
            for field in ['text', 'value', 'content', 'description', 'name', 'title', 'url']:
                if field in value:
                    return str(value[field])
            # If no common fields, return default
            return default
        if isinstance(value, (list, tuple)):
            return ' '.join(str(item) for item in value)
        return str(value)
    
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
                title = self._ensure_string(result.get('title', ''))
                url = self._ensure_string(result.get('url', ''))
                content = self._ensure_string(result.get('content', ''))[:200]
                text_snippets.append(f"Title: {title}\nURL: {url}\nContent: {content}")
        
        # Add funding search results
        if 'funding' in search_results:
            results = search_results['funding'].get('results', [])
            if not results and search_results['funding'].get('data'):
                results = search_results['funding']['data'].get('results', [])
            for result in results[:2]:
                title = self._ensure_string(result.get('title', ''))
                content = self._ensure_string(result.get('content', ''))[:200]
                text_snippets.append(f"Funding news: {title}\nContent: {content}")
        
        # Add website search results
        if 'website' in search_results:
            results = search_results['website'].get('results', [])
            if not results and search_results['website'].get('data'):
                results = search_results['website']['data'].get('results', [])
            for result in results[:3]:
                title = self._ensure_string(result.get('title', ''))
                url = self._ensure_string(result.get('url', ''))
                content = self._ensure_string(result.get('content', ''))[:200]
                text_snippets.append(f"Website search: {title}\nURL: {url}\nContent: {content}")
        
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

SELECTION RULES (PROMPT-ONLY, NO KEYWORD HEURISTICS):
1) If there are multiple similarly named entities, pick the single most likely company based on the request context and the fund profile (stage focus, typical check size, sector thesis, geography). Do not list multiple; select exactly one and proceed.
2) LinkedIn company/organization pages are a very strong disambiguation signal. Prefer entities that have a matching LinkedIn org page. Deprioritize OS features (e.g., Samsung DeX) or crypto exchanges unless the context clearly indicates those.
3) If confidence < 0.6, ask ONE brief clarification question; otherwise continue silently.
4) Only extract and return information about the selected company. Ignore similarly named products or platforms.

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
            if self.model_router:
                logger.info(f"Using model router for quick website identification of {company_name}")
                
                from app.services.model_router import ModelCapability
                result = await self.model_router.get_completion(
                    prompt=identification_prompt,
                    capability=ModelCapability.ANALYSIS,
                    max_tokens=500,
                    temperature=0,
                    caller_context="extraction"
                )
                response_text = result["response"]
                
                logger.info(f"Raw model router response for website ID: {response_text[:500]}")
                
                # Clean up response
                response_text = response_text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                
                # Additional cleanup for common Claude response patterns
                response_text = response_text.strip()
                if not response_text:
                    logger.warning("Empty response from model router for website identification")
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
                    url = self._ensure_string(result.get('url', ''))
                    if url and re.search(website_pattern, url, re.IGNORECASE):
                        return (url, None, 0.7)  # Let extraction determine business model
                    
                    # Check content
                    content = self._ensure_string(result.get('content', ''))
                    if content:
                        matches = re.findall(website_pattern, content, re.IGNORECASE)
                        if matches:
                            return (f"https://{matches[0]}", None, 0.6)  # Let extraction determine business model
        
        return ('', None, 0.0)