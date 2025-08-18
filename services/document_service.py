#!/usr/bin/env python3
"""
Document Processing Microservice
Handles PWERM analysis, full flow processing, and KYC verification
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import subprocess
from datetime import datetime
from typing import Dict, Any
import logging

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.services_dir = os.path.dirname(os.path.abspath(__file__))
        self.scripts_dir = os.path.join(os.path.dirname(self.services_dir), 'scripts')
        
    def run_pwerm_analysis(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run PWERM analysis using the pwerm_analysis.py script"""
        try:
            # Create temporary input file
            input_file = os.path.join(self.services_dir, 'temp_pwerm_input.json')
            with open(input_file, 'w') as f:
                json.dump(company_data, f)
            
            # Run PWERM analysis script
            cmd = [
                sys.executable,
                os.path.join(self.scripts_dir, 'pwerm_analysis.py'),
                '--input-file', input_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.scripts_dir)
            
            # Clean up temp file
            os.remove(input_file)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"PWERM analysis failed: {result.stderr}")
                return {'error': 'PWERM analysis failed', 'details': result.stderr}
                
        except Exception as e:
            logger.error(f"Error in PWERM analysis: {str(e)}")
            return {'error': f'PWERM analysis error: {str(e)}'}
    
    def run_full_flow_processing(self, document_path: str, document_id: str, document_type: str) -> Dict[str, Any]:
        """Run full flow processing using full_flow_no_comp.py script"""
        try:
            cmd = [
                sys.executable,
                os.path.join(self.scripts_dir, 'full_flow_no_comp.py'),
                '--process-file', document_path,
                document_id,
                document_type
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.scripts_dir)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Full flow processing failed: {result.stderr}")
                return {'error': 'Full flow processing failed', 'details': result.stderr}
                
        except Exception as e:
            logger.error(f"Error in full flow processing: {str(e)}")
            return {'error': f'Full flow processing error: {str(e)}'}
    
    def run_kyc_processing(self, document_path: str) -> Dict[str, Any]:
        """Run KYC processing using kyc_processor.py script"""
        try:
            cmd = [
                sys.executable,
                os.path.join(self.scripts_dir, 'kyc_processor.py'),
                document_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.scripts_dir)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"KYC processing failed: {result.stderr}")
                return {'error': 'KYC processing failed', 'details': result.stderr}
                
        except Exception as e:
            logger.error(f"Error in KYC processing: {str(e)}")
            return {'error': f'KYC processing error: {str(e)}'}

# Initialize processor
processor = DocumentProcessor()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'document-processor'
    })

@app.route('/api/pwerm/analyze', methods=['POST'])
def pwerm_analysis():
    """Endpoint for PWERM analysis"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        result = processor.run_pwerm_analysis(data)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in PWERM endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/document/process', methods=['POST'])
def process_document():
    """Endpoint for full document processing"""
    try:
        data = request.get_json()
        if not data or 'document_path' not in data:
            return jsonify({'error': 'Missing document_path'}), 400
        
        document_path = data['document_path']
        document_id = data.get('document_id', 'unknown')
        document_type = data.get('document_type', 'unknown')
        
        result = processor.run_full_flow_processing(document_path, document_id, document_type)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in document processing endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/kyc/process', methods=['POST'])
def kyc_processing():
    """Endpoint for KYC processing"""
    try:
        data = request.get_json()
        if not data or 'document_path' not in data:
            return jsonify({'error': 'Missing document_path'}), 400
        
        document_path = data['document_path']
        result = processor.run_kyc_processing(document_path)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in KYC endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/companies/load', methods=['POST'])
def load_companies():
    """Endpoint for loading companies data"""
    try:
        # This would typically load from a database or file
        # For now, return mock data
        companies_data = {
            'companies': [
                {
                    'id': '1',
                    'name': 'TechCorp Inc',
                    'sector': 'SaaS',
                    'stage': 'Series B',
                    'valuation': 50000000,
                    'funding_raised': 15000000,
                    'employees': 120,
                    'founded_year': 2020
                },
                {
                    'id': '2',
                    'name': 'FinTech Solutions',
                    'sector': 'Fintech',
                    'stage': 'Series A',
                    'valuation': 25000000,
                    'funding_raised': 8000000,
                    'employees': 45,
                    'founded_year': 2021
                }
            ],
            'total_count': 2,
            'loaded_at': datetime.now().isoformat()
        }
        
        return jsonify(companies_data)
        
    except Exception as e:
        logger.error(f"Error loading companies: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lps/load', methods=['POST'])
def load_lps():
    """Endpoint for loading LPs (Limited Partners) data"""
    try:
        # This would typically load from a database or file
        # For now, return mock data
        lps_data = {
            'lps': [
                {
                    'id': '1',
                    'name': 'University Endowment Fund',
                    'type': 'Endowment',
                    'total_commitment': 50000000,
                    'invested_amount': 35000000,
                    'remaining_commitment': 15000000,
                    'status': 'active'
                },
                {
                    'id': '2',
                    'name': 'Pension Fund Alpha',
                    'type': 'Pension Fund',
                    'total_commitment': 75000000,
                    'invested_amount': 60000000,
                    'remaining_commitment': 15000000,
                    'status': 'active'
                },
                {
                    'id': '3',
                    'name': 'Family Office Beta',
                    'type': 'Family Office',
                    'total_commitment': 25000000,
                    'invested_amount': 20000000,
                    'remaining_commitment': 5000000,
                    'status': 'active'
                }
            ],
            'total_count': 3,
            'total_commitment': 150000000,
            'total_invested': 115000000,
            'total_remaining': 35000000,
            'loaded_at': datetime.now().isoformat()
        }
        
        return jsonify(lps_data)
        
    except Exception as e:
        logger.error(f"Error loading LPs: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use port 3002 to avoid conflict with Next.js dev server
    port = int(os.environ.get('PORT', 3002))
    app.run(host='0.0.0.0', port=port, debug=False) 