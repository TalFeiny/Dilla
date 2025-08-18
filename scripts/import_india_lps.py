#!/usr/bin/env python3
"""
Import India LP data into Supabase
Creates high-net-worth individual LPs from India for fundraising
"""

import os
import sys
import csv
import re
from datetime import datetime
from supabase import create_client, Client

# Get Supabase credentials
SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Please set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def parse_net_worth(net_worth_str):
    """Parse net worth string and convert to USD amount"""
    if isinstance(net_worth_str, (int, float)):
        return int(net_worth_str * 1000000)  # Convert millions to dollars
    
    if not net_worth_str or net_worth_str == 'Unknown':
        return None
    
    # Clean string
    net_worth_str = str(net_worth_str).replace('$', '').replace(',', '').strip()
    
    # Handle different formats
    try:
        if 'B' in net_worth_str:
            amount = float(net_worth_str.replace('B', ''))
            return int(amount * 1000000000)  # Billions to dollars
        elif 'M' in net_worth_str:
            amount = float(net_worth_str.replace('M', ''))
            return int(amount * 1000000)  # Millions to dollars
        elif 'trillion' in net_worth_str.lower():
            amount = float(net_worth_str.split()[0])
            return int(amount * 1000000000000)  # Trillions to dollars
        else:
            return int(float(net_worth_str) * 1000000)  # Assume millions
    except:
        return None

def extract_linkedin_links(row):
    """Extract LinkedIn URLs from key person columns"""
    linkedin_links = []
    for key in ['Key Person', 'Key Person ', 'Key Person  ']:
        if key in row and row[key] and 'linkedin.com' in row[key]:
            linkedin_links.append(row[key])
    # Also check unnamed columns for LinkedIn links
    for key, value in row.items():
        if value and 'linkedin.com' in str(value) and value not in linkedin_links:
            linkedin_links.append(value)
    return linkedin_links

def import_india_lps():
    """Import India LP data from CSV file"""
    
    csv_file_path = '/Users/admin/Downloads/India LP list - Sheet1.csv'
    
    if not os.path.exists(csv_file_path):
        print(f"CSV file not found at: {csv_file_path}")
        # Fall back to hardcoded list
        india_lps = [
        # Tech Billionaires
        {
            'name': 'Mukesh Ambani',
            'company': 'Reliance Industries',
            'net_worth': '116B',
            'industry': 'Telecom, Retail, Energy',
            'focus': 'Technology, Digital Infrastructure',
            'notes': 'Chairman of Reliance, major investor in Jio Platforms'
        },
        {
            'name': 'Gautam Adani',
            'company': 'Adani Group',
            'net_worth': '84B',
            'industry': 'Infrastructure, Energy',
            'focus': 'Green Energy, Infrastructure Tech',
            'notes': 'Chairman of Adani Group, investing in renewable energy'
        },
        {
            'name': 'Shiv Nadar',
            'company': 'HCL Technologies',
            'net_worth': '36B',
            'industry': 'Technology',
            'focus': 'Enterprise Software, Education Tech',
            'notes': 'Founder of HCL, philanthropist focused on education'
        },
        {
            'name': 'Savitri Jindal',
            'company': 'Jindal Group',
            'net_worth': '33B',
            'industry': 'Steel, Power',
            'focus': 'Manufacturing Tech, Clean Energy',
            'notes': 'Chairperson of Jindal Group'
        },
        {
            'name': 'Cyrus Poonawalla',
            'company': 'Serum Institute',
            'net_worth': '21B',
            'industry': 'Healthcare, Vaccines',
            'focus': 'Biotech, Healthcare Innovation',
            'notes': 'Chairman of Serum Institute of India'
        },
        {
            'name': 'Dilip Shanghvi',
            'company': 'Sun Pharmaceuticals',
            'net_worth': '19B',
            'industry': 'Pharmaceuticals',
            'focus': 'Healthcare, Biotech',
            'notes': 'Founder of Sun Pharma'
        },
        {
            'name': 'Kumar Mangalam Birla',
            'company': 'Aditya Birla Group',
            'net_worth': '15B',
            'industry': 'Conglomerate',
            'focus': 'Fintech, Telecom, Fashion Tech',
            'notes': 'Chairman of Aditya Birla Group'
        },
        {
            'name': 'Radhakishan Damani',
            'company': 'DMart',
            'net_worth': '14B',
            'industry': 'Retail',
            'focus': 'Retail Tech, E-commerce',
            'notes': 'Founder of DMart retail chain'
        },
        {
            'name': 'Lakshmi Mittal',
            'company': 'ArcelorMittal',
            'net_worth': '14B',
            'industry': 'Steel',
            'focus': 'Manufacturing Tech, Sustainability',
            'notes': 'Executive Chairman of ArcelorMittal'
        },
        
        # Tech Entrepreneurs & VCs
        {
            'name': 'Azim Premji',
            'company': 'Wipro',
            'net_worth': '12B',
            'industry': 'Technology',
            'focus': 'Software, Social Impact',
            'notes': 'Founder of Wipro, major philanthropist'
        },
        {
            'name': 'Nandan Nilekani',
            'company': 'Infosys',
            'net_worth': '3.5B',
            'industry': 'Technology',
            'focus': 'Fintech, Digital Identity',
            'notes': 'Co-founder of Infosys, architect of Aadhaar'
        },
        {
            'name': 'Vijay Shekhar Sharma',
            'company': 'Paytm',
            'net_worth': '2.3B',
            'industry': 'Fintech',
            'focus': 'Payments, Financial Services',
            'notes': 'Founder of Paytm'
        },
        {
            'name': 'Byju Raveendran',
            'company': "BYJU'S",
            'net_worth': '2.1B',
            'industry': 'EdTech',
            'focus': 'Education Technology',
            'notes': "Founder of BYJU'S"
        },
        {
            'name': 'Ritesh Agarwal',
            'company': 'OYO',
            'net_worth': '1.1B',
            'industry': 'Hospitality Tech',
            'focus': 'Travel Tech, Real Estate Tech',
            'notes': 'Founder of OYO Rooms'
        },
        {
            'name': 'Nikhil Kamath',
            'company': 'Zerodha',
            'net_worth': '2.7B',
            'industry': 'Fintech',
            'focus': 'Financial Markets, Trading Tech',
            'notes': 'Co-founder of Zerodha'
        },
        {
            'name': 'Nithin Kamath',
            'company': 'Zerodha',
            'net_worth': '4.8B',
            'industry': 'Fintech',
            'focus': 'Capital Markets, Fintech',
            'notes': 'Founder & CEO of Zerodha'
        },
        {
            'name': 'Sachin Bansal',
            'company': 'Flipkart (Exited)',
            'net_worth': '1.4B',
            'industry': 'E-commerce',
            'focus': 'E-commerce, Fintech',
            'notes': 'Co-founder of Flipkart, active angel investor'
        },
        {
            'name': 'Binny Bansal',
            'company': 'Flipkart (Exited)',
            'net_worth': '1.4B',
            'industry': 'E-commerce',
            'focus': 'E-commerce, Logistics Tech',
            'notes': 'Co-founder of Flipkart, xto10x founder'
        },
        
        # Family Offices & Investment Groups
        {
            'name': 'Ratan Tata',
            'company': 'Tata Group',
            'net_worth': '1B',
            'industry': 'Conglomerate',
            'focus': 'Tech Startups, Social Impact',
            'notes': 'Chairman Emeritus of Tata, active angel investor'
        },
        {
            'name': 'Narayana Murthy',
            'company': 'Infosys',
            'net_worth': '4.4B',
            'industry': 'Technology',
            'focus': 'Deep Tech, Enterprise Software',
            'notes': 'Founder of Infosys, Catamaran Ventures'
        },
        {
            'name': 'Kiran Mazumdar-Shaw',
            'company': 'Biocon',
            'net_worth': '2.5B',
            'industry': 'Biotechnology',
            'focus': 'Healthcare, Biotech',
            'notes': 'Founder of Biocon'
        },
        {
            'name': 'Uday Kotak',
            'company': 'Kotak Mahindra Bank',
            'net_worth': '13B',
            'industry': 'Banking',
            'focus': 'Fintech, Financial Services',
            'notes': 'Founder of Kotak Mahindra Bank'
        },
        {
            'name': 'Harsh Mariwala',
            'company': 'Marico',
            'net_worth': '2.6B',
            'industry': 'FMCG',
            'focus': 'Consumer Tech, D2C Brands',
            'notes': 'Founder of Marico, runs Sharrp Ventures'
        },
        {
            'name': 'Ronnie Screwvala',
            'company': 'UTV Group',
            'net_worth': '1.5B',
            'industry': 'Media',
            'focus': 'EdTech, Media Tech',
            'notes': 'Serial entrepreneur, founder of upGrad'
        },
        {
            'name': 'Anand Mahindra',
            'company': 'Mahindra Group',
            'net_worth': '2B',
            'industry': 'Automotive',
            'focus': 'Mobility, Clean Tech',
            'notes': 'Chairman of Mahindra Group'
        }
    ]
    
    print(f"Importing {len(india_lps)} India LPs...")
    
    success_count = 0
    error_count = 0
    
    for lp in india_lps:
        try:
            # Create LP record
            lp_record = {
                'name': lp['name'],
                'lp_type': 'Individual',
                'contact_name': lp['name'],
                'contact_email': None,
                'contact_phone': None,
                'relationship_start_date': None,
                'investment_capacity_usd': parse_net_worth(lp['net_worth']),
                'investment_focus': {
                    'company': lp['company'],
                    'industry': lp['industry'],
                    'focus_areas': lp['focus'],
                    'notes': lp['notes'],
                    'geography': 'India',
                    'type': 'High Net Worth Individual'
                },
                'lpc_member': False,
                'lpc_role': None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert into database
            result = supabase.table('lps').insert(lp_record).execute()
            
            if result.data:
                success_count += 1
                print(f"✅ Imported: {lp['name']} (${lp['net_worth']})")
            else:
                error_count += 1
                print(f"❌ Failed to import: {lp['name']}")
                
        except Exception as e:
            error_count += 1
            print(f"❌ Error importing {lp['name']}: {str(e)}")
    
    print(f"\n✅ Import complete: {success_count} successful, {error_count} errors")
    
    # Verify import
    try:
        result = supabase.table('lps').select('name', 'investment_capacity_usd').execute()
        if result.data:
            india_lps = [lp for lp in result.data if lp.get('investment_focus', {}).get('geography') == 'India']
            total_capacity = sum(lp['investment_capacity_usd'] for lp in result.data if lp['investment_capacity_usd'])
            print(f"\n📊 Total LPs in database: {len(result.data)}")
            print(f"💰 Total investment capacity: ${total_capacity:,.0f}")
    except Exception as e:
        print(f"Error verifying import: {str(e)}")

if __name__ == '__main__':
    import_india_lps()