#!/usr/bin/env python3
"""
Script to save publicSAAScompanies.com data

Usage:
1. Go to https://www.publicsaascompanies.com/
2. Click the "Copy" button to copy all data
3. Run this script: python save_public_saas_data.py
4. Paste the data when prompted
5. The data will be saved to data/public_saas_companies.csv
"""

import os
import sys

def save_public_saas_data():
    print("=== PublicSAASCompanies.com Data Saver ===")
    print("\nInstructions:")
    print("1. Go to https://www.publicsaascompanies.com/")
    print("2. Click the 'Copy' button to copy the table data")
    print("3. Paste the data here (press Ctrl+D or Cmd+D when done):\n")
    
    # Read from stdin until EOF
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    if not lines:
        print("No data received!")
        return
    
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Save to CSV file
    csv_path = os.path.join(data_dir, 'public_saas_companies.csv')
    
    with open(csv_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"\n✓ Data saved to: {csv_path}")
    print(f"✓ Total rows: {len(lines)}")
    
    # Show preview
    if len(lines) > 1:
        print("\nPreview of saved data:")
        print("Headers:", lines[0][:100] + "..." if len(lines[0]) > 100 else lines[0])
        print("First row:", lines[1][:100] + "..." if len(lines[1]) > 100 else lines[1])

if __name__ == "__main__":
    save_public_saas_data()