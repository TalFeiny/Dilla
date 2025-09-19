import asyncio
import os
from dotenv import load_dotenv
from tavily import AsyncTavilyClient

load_dotenv()

async def test_dwelly_search():
    client = AsyncTavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
    
    queries = [
        '"Dwelly" startup company',
        '"Dwelly" lettings property management UK',
        'Dwelly.group',
        'Dwelly.io'
    ]
    
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        
        try:
            result = await client.search(
                query=query,
                search_depth="advanced",
                max_results=3
            )
            
            for r in result.get('results', []):
                print(f"\nTitle: {r['title']}")
                print(f"URL: {r['url']}")
                print(f"Content: {r['content'][:300]}...")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_dwelly_search())