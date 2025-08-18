"""
CrewAI-based Agent System for VC Platform
Multiple specialized agents working together for comprehensive analysis
"""

from crewai import Agent, Task, Crew, Process
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from typing import Dict, List, Any
import os
import json
import requests
from datetime import datetime

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# Custom Tools for Agents
class VCPlatformTools:
    """Custom tools for VC platform operations"""
    
    @staticmethod
    def search_market_data(query: str) -> str:
        """Search for market data using Tavily"""
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            return "Tavily API key not configured"
        
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": True
                }
            )
            data = response.json()
            return json.dumps({
                "answer": data.get("answer"),
                "sources": [{"title": r["title"], "url": r["url"]} for r in data.get("results", [])]
            })
        except Exception as e:
            return f"Search error: {str(e)}"
    
    @staticmethod
    def analyze_company_metrics(company_name: str, arr: float, growth_rate: float) -> str:
        """Analyze company metrics and calculate key indicators"""
        try:
            # Calculate key metrics
            arr_multiple = 10  # Default SaaS multiple
            valuation = arr * arr_multiple
            burn_multiple = 1.5 if growth_rate > 1.0 else 2.0
            
            metrics = {
                "company": company_name,
                "current_arr": arr,
                "growth_rate": growth_rate,
                "estimated_valuation": valuation,
                "arr_multiple": arr_multiple,
                "burn_multiple": burn_multiple,
                "rule_of_40": (growth_rate * 100) + 20,  # Assuming 20% profit margin
                "magic_number": growth_rate / burn_multiple
            }
            return json.dumps(metrics)
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    @staticmethod
    def query_portfolio_database(query_type: str, filters: Dict = None) -> str:
        """Query portfolio database (mock implementation)"""
        # This would connect to Supabase in production
        mock_data = {
            "portfolio_companies": [
                {"name": "Company A", "sector": "SaaS", "arr": 10000000, "growth": 1.5},
                {"name": "Company B", "sector": "Fintech", "arr": 5000000, "growth": 2.0}
            ],
            "recent_exits": [
                {"company": "ExitCo", "multiple": 15, "acquirer": "BigCorp"}
            ]
        }
        return json.dumps(mock_data.get(query_type, {}))
    
    @staticmethod
    def generate_investment_memo(data: Dict) -> str:
        """Generate structured investment memo"""
        memo = f"""
# Investment Memo: {data.get('company_name', 'Unknown')}
Generated: {datetime.now().isoformat()}

## Executive Summary
{data.get('summary', 'No summary provided')}

## Market Analysis
{data.get('market_analysis', 'No market analysis')}

## Financial Metrics
- ARR: ${data.get('arr', 0):,.0f}
- Growth Rate: {data.get('growth_rate', 0)*100:.1f}%
- Valuation: ${data.get('valuation', 0):,.0f}

## Risks & Opportunities
{data.get('risks', 'No risks identified')}

## Recommendation
{data.get('recommendation', 'No recommendation')}
"""
        return memo

# Create tools for agents
search_tool = Tool(
    name="Search Market Data",
    func=VCPlatformTools.search_market_data,
    description="Search for market data, competitors, and industry trends"
)

analyze_tool = Tool(
    name="Analyze Metrics",
    func=VCPlatformTools.analyze_company_metrics,
    description="Analyze company metrics and calculate key indicators"
)

database_tool = Tool(
    name="Query Database",
    func=lambda x: VCPlatformTools.query_portfolio_database("portfolio_companies"),
    description="Query portfolio database for company information"
)

memo_tool = Tool(
    name="Generate Memo",
    func=lambda x: VCPlatformTools.generate_investment_memo(json.loads(x)),
    description="Generate structured investment memo"
)

# Define Specialized Agents
class VCAgents:
    """Collection of specialized VC platform agents"""
    
    @staticmethod
    def create_market_researcher():
        """Agent specialized in market research and competitive analysis"""
        return Agent(
            role="Market Research Analyst",
            goal="Conduct comprehensive market research and competitive analysis",
            backstory="""You are an experienced market research analyst with deep expertise 
            in technology markets, particularly SaaS, Fintech, and AI sectors. You excel at 
            finding relevant market data, identifying trends, and analyzing competitive landscapes.""",
            verbose=True,
            allow_delegation=False,
            tools=[search_tool],
            llm=llm
        )
    
    @staticmethod
    def create_financial_analyst():
        """Agent specialized in financial analysis and metrics"""
        return Agent(
            role="Financial Analyst",
            goal="Analyze financial metrics and calculate valuations",
            backstory="""You are a seasoned financial analyst with expertise in venture capital 
            and growth equity. You specialize in SaaS metrics, unit economics, and valuation 
            methodologies. You can quickly assess company performance and growth potential.""",
            verbose=True,
            allow_delegation=False,
            tools=[analyze_tool, database_tool],
            llm=llm
        )
    
    @staticmethod
    def create_due_diligence_lead():
        """Agent that coordinates due diligence process"""
        return Agent(
            role="Due Diligence Lead",
            goal="Coordinate comprehensive due diligence and risk assessment",
            backstory="""You are a senior investment professional who leads due diligence 
            processes. You excel at identifying risks, validating assumptions, and ensuring 
            thorough analysis before investment decisions.""",
            verbose=True,
            allow_delegation=True,
            tools=[search_tool, database_tool],
            llm=llm
        )
    
    @staticmethod
    def create_investment_strategist():
        """Agent that develops investment thesis and recommendations"""
        return Agent(
            role="Investment Strategist",
            goal="Develop investment thesis and strategic recommendations",
            backstory="""You are a partner-level investment strategist with deep experience 
            in venture capital. You synthesize research, financial analysis, and market dynamics 
            to develop compelling investment theses and strategic recommendations.""",
            verbose=True,
            allow_delegation=False,
            tools=[memo_tool],
            llm=llm
        )

# Create Tasks for Different Workflows
class VCTasks:
    """Collection of tasks for VC workflows"""
    
    @staticmethod
    def market_research_task(company_name: str, sector: str):
        """Task for comprehensive market research"""
        return Task(
            description=f"""
            Conduct comprehensive market research for {company_name} in the {sector} sector:
            1. Search for total addressable market (TAM) and growth rates
            2. Identify key competitors and their funding/valuations
            3. Analyze market trends and dynamics
            4. Find recent M&A activity and exit multiples
            5. Identify potential strategic acquirers
            
            Provide a structured report with sources cited.
            """,
            expected_output="Detailed market research report with TAM, competitors, trends, and exit comparables",
            agent=VCAgents.create_market_researcher()
        )
    
    @staticmethod
    def financial_analysis_task(company_name: str, arr: float, growth_rate: float):
        """Task for financial analysis"""
        return Task(
            description=f"""
            Analyze financial metrics for {company_name}:
            - Current ARR: ${arr:,.0f}
            - Growth Rate: {growth_rate*100:.1f}%
            
            Calculate:
            1. Appropriate valuation multiples based on growth
            2. Rule of 40 score
            3. Burn multiple and efficiency metrics
            4. Comparison to portfolio companies
            5. Projected future valuations
            
            Provide detailed financial assessment.
            """,
            expected_output="Comprehensive financial analysis with metrics and valuations",
            agent=VCAgents.create_financial_analyst()
        )
    
    @staticmethod
    def due_diligence_task(company_name: str, research_output: str, financial_output: str):
        """Task for due diligence coordination"""
        return Task(
            description=f"""
            Lead due diligence for {company_name} based on:
            - Market Research: {research_output}
            - Financial Analysis: {financial_output}
            
            Identify:
            1. Key risks and red flags
            2. Growth opportunities
            3. Competitive advantages
            4. Required follow-up diligence items
            5. Critical success factors
            
            Provide risk-adjusted assessment.
            """,
            expected_output="Due diligence report with risks, opportunities, and recommendations",
            agent=VCAgents.create_due_diligence_lead()
        )
    
    @staticmethod
    def investment_memo_task(company_name: str, all_outputs: Dict):
        """Task for creating investment memo"""
        return Task(
            description=f"""
            Create comprehensive investment memo for {company_name} synthesizing all analysis:
            {json.dumps(all_outputs, indent=2)}
            
            Structure the memo with:
            1. Executive Summary
            2. Investment Thesis
            3. Market Opportunity
            4. Financial Analysis
            5. Risks and Mitigations
            6. Strategic Rationale
            7. Recommendation (Invest/Pass with reasoning)
            
            Make it compelling and data-driven.
            """,
            expected_output="Professional investment memo with clear recommendation",
            agent=VCAgents.create_investment_strategist()
        )

# Create Crews for Different Workflows
class VCCrews:
    """Collection of crews for different VC workflows"""
    
    @staticmethod
    def create_full_analysis_crew(company_name: str, arr: float, growth_rate: float, sector: str):
        """Create crew for full company analysis"""
        
        # Create agents
        market_researcher = VCAgents.create_market_researcher()
        financial_analyst = VCAgents.create_financial_analyst()
        dd_lead = VCAgents.create_due_diligence_lead()
        strategist = VCAgents.create_investment_strategist()
        
        # Create tasks
        market_task = VCTasks.market_research_task(company_name, sector)
        financial_task = VCTasks.financial_analysis_task(company_name, arr, growth_rate)
        
        # Create crew
        crew = Crew(
            agents=[market_researcher, financial_analyst, dd_lead, strategist],
            tasks=[market_task, financial_task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew
    
    @staticmethod
    def create_quick_assessment_crew(company_name: str, sector: str):
        """Create crew for quick market assessment"""
        
        # Create focused agents
        market_researcher = VCAgents.create_market_researcher()
        
        # Create focused task
        task = Task(
            description=f"""
            Quick market assessment for {company_name} in {sector}:
            1. Market size and growth
            2. Top 5 competitors
            3. Recent funding rounds
            4. Exit comparables
            
            Provide concise summary with key insights.
            """,
            expected_output="Concise market assessment with key metrics",
            agent=market_researcher
        )
        
        crew = Crew(
            agents=[market_researcher],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        return crew

# Main execution function
def run_vc_analysis(company_name: str, arr: float, growth_rate: float, sector: str, analysis_type: str = "full"):
    """
    Run VC analysis using CrewAI
    
    Args:
        company_name: Name of the company
        arr: Annual Recurring Revenue in millions
        growth_rate: Annual growth rate (e.g., 0.8 for 80%)
        sector: Company sector
        analysis_type: "full" or "quick"
    
    Returns:
        Analysis results as dictionary
    """
    
    try:
        if analysis_type == "full":
            crew = VCCrews.create_full_analysis_crew(company_name, arr * 1000000, growth_rate, sector)
        else:
            crew = VCCrews.create_quick_assessment_crew(company_name, sector)
        
        # Execute the crew
        result = crew.kickoff()
        
        return {
            "success": True,
            "company": company_name,
            "analysis_type": analysis_type,
            "timestamp": datetime.now().isoformat(),
            "results": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 5:
        print("Usage: python crewai_agents.py <company_name> <arr_millions> <growth_rate> <sector>")
        sys.exit(1)
    
    company = sys.argv[1]
    arr = float(sys.argv[2])
    growth = float(sys.argv[3])
    sector = sys.argv[4]
    
    result = run_vc_analysis(company, arr, growth, sector)
    print(json.dumps(result, indent=2))