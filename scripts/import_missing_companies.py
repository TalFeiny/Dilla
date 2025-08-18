import csv
import sys
import os
import uuid
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env.local')

# Initialize Supabase
url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

# Allow large CSV fields
csv.field_size_limit(sys.maxsize)

# Read the CSV file
csv_path = '/Users/admin/Downloads/Secos 2 - Imported table-Grid view.csv'
print(f"Reading CSV from {csv_path}")

companies_to_add = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        company_name = row.get('Company', '').strip()
        if not company_name:
            continue
            
        # Only process companies starting with N-Z
        if company_name[0].upper() < 'N':
            continue
            
        # Extract data from CSV
        sector = row.get('Sector', 'Technology').strip() or 'Technology'
        amount_raised = row.get('Amount Raised', '').strip()
        quarter = row.get('Raised', '').strip()
        country = row.get('Country', '').strip()
        revenue = row.get('Revenue (M$)', '').strip()
        growth = row.get('Growth Rate', '').strip()
        
        # Parse amount raised
        amount_usd = 0
        if amount_raised:
            # Remove currency symbols and convert
            amount_str = amount_raised.replace('$', '').replace('M', '').replace(',', '')
            try:
                if amount_str and amount_str != '0.00':
                    amount_usd = float(amount_str) * 1000000  # Convert to USD
            except:
                pass
        
        companies_to_add.append({
            'name': company_name,
            'sector': sector,
            'amount_raised': amount_usd if amount_usd > 0 else None,
            'quarter_raised': quarter if quarter else None,
            'country': country,
            'revenue': revenue,
            'growth': growth
        })

print(f"Found {len(companies_to_add)} companies starting with N-Z")

# Get existing companies from database
existing = supabase.table('companies').select('name').execute()
existing_names = set(c['name'] for c in existing.data)
print(f"Existing companies in database: {len(existing_names)}")

# Filter to only new companies
new_companies = [c for c in companies_to_add if c['name'] not in existing_names]
print(f"New companies to add: {len(new_companies)}")

# Get organization ID from existing company
if len(existing.data) > 0:
    org_result = supabase.table('companies').select('organization_id').limit(1).execute()
    org_id = org_result.data[0]['organization_id']
    print(f"Using organization ID: {org_id}")
    
    # Prepare for database insertion
    companies_to_insert = []
    for company in new_companies:
        companies_to_insert.append({
            'id': str(uuid.uuid4()),
            'organization_id': org_id,
            'name': company['name'],
            'sector': company['sector'],
            'amount_raised': company['amount_raised'],
            'quarter_raised': company['quarter_raised'],
            'location': {
                'geography': company['country'] if company['country'] else 'Global',
                'data_source': 'csv_import',
                'amount_raised_usd': company['amount_raised'] if company['amount_raised'] else None
            },
            'status': 'active'
        })
    
    # Insert in batches
    batch_size = 50
    for i in range(0, len(companies_to_insert), batch_size):
        batch = companies_to_insert[i:i+batch_size]
        try:
            result = supabase.table('companies').insert(batch).execute()
            print(f"Inserted batch {i//batch_size + 1}: {len(batch)} companies")
        except Exception as e:
            print(f"Error inserting batch {i//batch_size + 1}: {e}")
    
    # Verify final count
    final_count = supabase.table('companies').select('id', count='exact').execute()
    print(f"\nFinal total companies in database: {final_count.count}")
    
    # Check distribution
    all_companies = supabase.table('companies').select('name').execute()
    names = sorted(set(c['name'] for c in all_companies.data))
    
    print(f"\nUnique companies: {len(names)}")
    print("Distribution by letter:")
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        count = len([n for n in names if n[0].upper() == letter])
        if count > 0:
            print(f"  {letter}: {count} companies")
else:
    print("No existing companies found to get organization ID")