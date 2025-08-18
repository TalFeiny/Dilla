from http.server import BaseHTTPRequestHandler
import json
import sys
import os
from datetime import datetime

# Add the scripts directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from pwerm_analysis import PWERMAnalyzer as IntelligentPWERMAnalyzer
except ImportError:
    # Fallback for when running in Vercel
    pass

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            # Extract parameters
            company_name = request_data.get('company_name', 'Unknown Company')
            current_arr = request_data.get('current_arr_usd', 5000000) / 1000000  # Convert to millions
            growth_rate = request_data.get('growth_rate', 0.30)
            sector = request_data.get('sector', 'Technology')
            assumptions = request_data.get('assumptions', {})
            
            # Initialize analyzer
            tavily_api_key = os.getenv('TAVILY_API_KEY')
            openai_api_key = os.getenv('OPENAI_API_KEY')
            analyzer = IntelligentPWERMAnalyzer(tavily_api_key, openai_api_key)
            
            # Prepare company data
            company_data = {
                'name': company_name,
                'revenue': current_arr,
                'growth_rate': growth_rate,
                'sector': sector,
                'funding': 10.0,  # Default
                'data_confidence': 'medium'
            }
            
            # Run analysis
            print(f"Starting PWERM analysis for {company_name}...", file=sys.stderr)
            results = analyzer.run_pwerm_analysis(company_data, assumptions)
            
            # Prepare output
            output = {
                'success': True,
                'core_inputs': {
                    'company_name': company_name,
                    'current_arr_usd': current_arr * 1000000,
                    'growth_rate': growth_rate,
                    'sector': sector
                },
                'market_research': results['market_research'],
                'scenarios': results['scenarios'],
                'charts': results['charts'],
                'summary': results['summary'],
                'analysis_timestamp': results['analysis_timestamp'],
                'progress': [
                    'Starting PWERM analysis...',
                    'Researching company details...',
                    'Analyzing sector M&A activity...',
                    'Calculating 499 scenario probabilities...',
                    'Normalizing probability distribution...',
                    'Analysis completed successfully!'
                ]
            }
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.end_headers()
            self.wfile.write(json.dumps(output).encode())
            
        except Exception as e:
            import traceback
            error_output = {
                'error': f'PWERM analysis failed: {str(e)}',
                'traceback': traceback.format_exc(),
                'progress': ['Analysis failed']
            }
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(error_output).encode())
    
    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers() 