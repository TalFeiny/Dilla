#!/usr/bin/env python3
import json
import sys
import requests

# The deck data from your last curl output
deck_data = {
    "slides": [
        {
            "id": "slide-1",
            "order": 1,
            "template": "title",
            "content": {
                "title": "Investment Analysis Report",
                "subtitle": "Analysis of 2 companies",
                "date": "October 2025"
            }
        }
    ],
    "format": "deck",
    "theme": "professional",
    "companies": ["@Cuspai", "@Exactlyai"]
}

# Export to PDF
response = requests.post(
    'http://localhost:8000/api/export/deck',
    json={
        "deck_data": deck_data,
        "format": "pdf"
    }
)

if response.status_code == 200:
    with open('deck.pdf', 'wb') as f:
        f.write(response.content)
    print("✅ PDF exported to deck.pdf")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

