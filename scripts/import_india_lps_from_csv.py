#!/usr/bin/env python3
"""
Import India LP data from CSV file into Supabase
Reads the full 200+ LP list from CSV
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
    if not net_worth_str or net_worth_str == 'Unknown' or net_worth_str == '':
        return None
    
    # Clean string - remove $ and commas
    net_worth_str = str(net_worth_str).replace('$', '').replace(',', '').strip()
    
    # Handle different formats
    try:
        if 'T' in net_worth_str or 'trillion' in net_worth_str.lower():
            # Trillions
            amount = float(re.findall(r'[\d.]+', net_worth_str)[0])
            return int(amount * 1000000000000)  # Convert to dollars
        elif 'B' in net_worth_str or 'billion' in net_worth_str.lower():
            # Billions
            amount = float(re.findall(r'[\d.]+', net_worth_str)[0])
            return int(amount * 1000000000)  # Convert to dollars
        elif 'M' in net_worth_str or 'million' in net_worth_str.lower():
            # Millions
            amount = float(re.findall(r'[\d.]+', net_worth_str)[0])
            return int(amount * 1000000)  # Convert to dollars
        else:
            # Try to parse as number (assume millions if no suffix)
            amount = float(re.findall(r'[\d.]+', net_worth_str)[0])
            if amount < 1000:  # If less than 1000, probably in millions
                return int(amount * 1000000)
            else:
                return int(amount)
    except:
        return None

def extract_linkedin_links(row):
    """Extract LinkedIn URLs from all columns"""
    linkedin_links = []
    for key, value in row.items():
        if value and 'linkedin.com' in str(value):
            # Clean and add the link
            link = str(value).strip()
            if link not in linkedin_links:
                linkedin_links.append(link)
    return linkedin_links

def import_india_lps_from_csv():
    """Import India LP data from CSV file"""
    
    csv_file_path = '/Users/admin/Downloads/India LP list - Sheet1.csv'
    
    if not os.path.exists(csv_file_path):
        print(f"❌ CSV file not found at: {csv_file_path}")
        return
    
    print(f"📂 Reading CSV file: {csv_file_path}")
    
    lps_to_import = []
    
    # Read CSV file
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            # Skip empty rows
            if not row.get('Name') or row['Name'].strip() == '':
                continue
            
            # Parse net worth
            investment_capacity = parse_net_worth(row.get('Net Worth', ''))
            
            # Extract LinkedIn links
            linkedin_links = extract_linkedin_links(row)
            
            # Create investment focus object
            investment_focus = {
                'industry': row.get('Industry', '').strip() if row.get('Industry') else None,
                'notes': row.get('Notes', '').strip() if row.get('Notes') else None,
                'linkedin_contacts': linkedin_links,
                'geography': 'India',
                'type': 'High Net Worth Individual'
            }
            
            # Create LP record
            lp_record = {
                'name': row['Name'].strip(),
                'lp_type': 'Individual',
                'contact_name': row['Name'].strip(),
                'contact_email': None,
                'contact_phone': None,
                'relationship_start_date': None,
                'investment_capacity_usd': investment_capacity,
                'investment_focus': investment_focus,
                'lpc_member': False,
                'lpc_role': None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            lps_to_import.append(lp_record)
    
    print(f"📊 Found {len(lps_to_import)} LPs to import")
    
    # Import to database
    success_count = 0
    error_count = 0
    
    for lp in lps_to_import:
        try:
            # Check if LP already exists
            existing = supabase.table('lps').select('id').eq('name', lp['name']).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing LP
                result = supabase.table('lps').update(lp).eq('name', lp['name']).execute()
                print(f"📝 Updated: {lp['name']}")
            else:
                # Insert new LP
                result = supabase.table('lps').insert(lp).execute()
                print(f"✅ Imported: {lp['name']} (${lp['investment_capacity_usd']:,})" if lp['investment_capacity_usd'] else f"✅ Imported: {lp['name']}")
            
            if result.data:
                success_count += 1
            else:
                error_count += 1
                print(f"❌ Failed: {lp['name']}")
                
        except Exception as e:
            error_count += 1
            print(f"❌ Error with {lp['name']}: {str(e)}")
    
    print(f"\n✅ Import complete!")
    print(f"📊 Results: {success_count} successful, {error_count} errors")
    
    # Verify import and show stats
    try:
        result = supabase.table('lps').select('name', 'investment_capacity_usd', 'investment_focus').execute()
        if result.data:
            india_lps = [lp for lp in result.data if lp.get('investment_focus', {}).get('geography') == 'India']
            total_capacity = sum(lp['investment_capacity_usd'] for lp in india_lps if lp.get('investment_capacity_usd'))
            
            print(f"\n📈 Database Stats:")
            print(f"   Total India LPs: {len(india_lps)}")
            print(f"   Total LPs in database: {len(result.data)}")
            print(f"   💰 Total India LP capacity: ${total_capacity:,.0f}")
            
            # Show top 5 by capacity
            sorted_lps = sorted([lp for lp in india_lps if lp.get('investment_capacity_usd')], 
                              key=lambda x: x['investment_capacity_usd'], reverse=True)[:5]
            
            print(f"\n🏆 Top 5 India LPs by capacity:")
            for lp in sorted_lps:
                print(f"   {lp['name']}: ${lp['investment_capacity_usd']:,.0f}")
                
    except Exception as e:
        print(f"Error verifying import: {str(e)}")

if __name__ == '__main__':
    import_india_lps_from_csv()