#!/usr/bin/env python3
import json

with open('deel_output_v2.json', 'r') as f:
    data = json.load(f)
    
mr = data['market_research']

print('EXIT COMPARABLES FOUND:')
exits = mr.get('exit_comparables', [])
print(f'Total: {len(exits)} deals\n')

for i, exit in enumerate(exits[:10]):
    print(f'{i+1}. {exit["target"]} → {exit["acquirer"]}')
    if exit.get('deal_value'):
        print(f'   Value: ${exit["deal_value"]}M')
    if exit.get('revenue_multiple'):
        print(f'   Multiple: {exit["revenue_multiple"]}x')
    print(f'   Details: {exit.get("details", "")}')
    print()