import asyncio
from anthropic import AsyncAnthropic
import json
import re

async def test():
    client = AsyncAnthropic()
    
    # The exact prompt the system uses
    prompt = """Extract EVERYTHING about Dwelly from these search results. Be EXHAUSTIVE.

SEARCH RESULTS:
[GENERAL - Dwelly acquires Lime Property Management]:
URL: https://techcrunch.com/dwelly-lime-acquisition
UK-based proptech startup Dwelly has acquired Lime Property Management as part of its AI-powered roll-up strategy in the home services sector. The company, founded by ex-Uber executives, is building an AI-enhanced property management platform. Visit their website at dwelly.group for more information.
---

[WEBSITE - Dwelly Group - AI Property Management]:
URL: https://dwelly.group
Dwelly Group is revolutionizing property management through AI and strategic acquisitions. Our platform combines the best of traditional property management with cutting-edge AI technology.
---

EXTRACTION INSTRUCTIONS:
Read EVERY search result carefully. Extract ALL information mentioned about Dwelly, including:

1. BUSINESS MODEL: What exactly do they do? How do they make money? What's their strategy (e.g., roll-up, marketplace, SaaS)?
2. ACQUISITIONS & DEALS: List EVERY company they've acquired or partnered with. Include dates and deal sizes if mentioned.
3. FOUNDERS & TEAM: Names, backgrounds (e.g., "ex-Uber"), roles, any other companies they've worked at
4. INVESTORS: ALL investors mentioned, funding rounds, amounts raised, valuations
5. METRICS: Revenue, growth rate, user numbers, efficiency gains (e.g., "3x faster"), market share, ANY numbers
6. CUSTOMERS: Who uses their product? Any specific companies mentioned?
7. GEOGRAPHY: Where are they based? Where do they operate?
8. PRODUCT DETAILS: Features, technology used, integrations, pricing if mentioned
9. COMPETITORS: Any competitors mentioned or compared to
10. NEWS & MILESTONES: Product launches, expansions, partnerships, awards
11. WEBSITE: Any website URLs mentioned in the articles

IMPORTANT: 
- If something is mentioned ANYWHERE in the search results, include it
- Include specific names, numbers, and dates
- If "Dwelly acquires Lime Property" is mentioned, that MUST be in acquisitions
- If "reduces time by 3x" is mentioned, that MUST be in metrics
- Don't summarize - extract the actual facts

Return a JSON with ALL extracted information. Use arrays for lists (acquisitions, investors, etc).
Every fact you find should be included. Be comprehensive, not selective."""

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=3000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    profile_text = response.content[0].text.strip()
    print("=== RAW CLAUDE RESPONSE ===")
    print(profile_text[:1000])
    print("\n=== ATTEMPTING JSON EXTRACTION ===")
    
    # Try the simple regex first
    simple_match = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', profile_text, re.DOTALL)
    if simple_match:
        print(f"Simple regex found JSON at position {simple_match.start()}-{simple_match.end()}")
        try:
            profile = json.loads(simple_match.group(0))
            print("✅ Simple regex worked!")
            print(f"Keys found: {list(profile.keys())}")
        except:
            print("❌ Simple regex found something but it's not valid JSON")
    
    # Try a more comprehensive approach
    # Look for JSON that starts with { and ends with the last }
    if '{' in profile_text and '}' in profile_text:
        start = profile_text.find('{')
        end = profile_text.rfind('}') + 1
        potential_json = profile_text[start:end]
        try:
            profile = json.loads(potential_json)
            print("\n✅ Full extraction worked!")
            print(f"Keys: {list(profile.keys())}")
            print(f"Business Model: {profile.get('business_model', 'NOT FOUND')}")
            print(f"Acquisitions: {profile.get('acquisitions', 'NOT FOUND')}")
            print(f"Geography: {profile.get('geography', 'NOT FOUND')}")
            print(f"Website: {profile.get('website', 'NOT FOUND')}")
        except Exception as e:
            print(f"\n❌ Full extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())