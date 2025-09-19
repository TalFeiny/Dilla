#!/bin/bash

# Test Format Handlers with GPU Cost Spectrum
# Testing the spectrum from low AI (10%) to high AI (Gamma-like 40%+ margins)

API_URL="http://localhost:3001/api/agent/unified-brain"

echo "🚀 Testing GPU Cost Spectrum in Format Handlers"
echo "================================================"
echo ""
echo "Spectrum:"
echo "  📊 Low GPU (10%): Traditional SaaS with light AI"
echo "  🔍 Medium GPU (25%): Search/synthesis companies"  
echo "  💻 High GPU (40%+): Code generation (Gamma-like)"
echo ""

# Function to test a specific format
test_format() {
    local prompt="$1"
    local format="$2"
    local test_name="$3"
    
    echo "📝 Testing $test_name - Format: $format"
    echo "   Prompt: $prompt"
    
    response=$(curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{
            \"prompt\": \"$prompt\",
            \"output_format\": \"$format\",
            \"context\": {
                \"includeGPUAnalysis\": true,
                \"includeMarginImpact\": true
            }
        }")
    
    # Check if response is valid JSON
    if echo "$response" | jq -e . > /dev/null 2>&1; then
        echo "   ✅ Valid JSON response received"
        
        # Extract key metrics
        has_result=$(echo "$response" | jq -r '.result != null')
        has_citations=$(echo "$response" | jq -r '.citations != null')
        companies=$(echo "$response" | jq -r '.metadata.companies // [] | join(", ")')
        
        echo "   - Has result: $has_result"
        echo "   - Has citations: $has_citations"
        if [ -n "$companies" ]; then
            echo "   - Companies: $companies"
        fi
        
        # Look for GPU metrics in the response
        if [ "$format" == "analysis" ]; then
            echo "$response" | jq -r '.result.companies | to_entries[] | 
                "   💰 \(.key): 
                    - Business Model: \(.value.business_model // "N/A")
                    - GPU Intensity: \(.value.gpu_metrics.compute_intensity // "N/A")
                    - Margin Impact: \(.value.gross_margin_analysis.margin_impact // "N/A")"' 2>/dev/null
        fi
    else
        echo "   ❌ Invalid response or server error"
    fi
    
    echo ""
}

echo "================== HIGH GPU TEST =================="
echo "Testing code generation companies (Cursor, Lovable, Replit)"
echo ""
test_format "Analyze @Cursor @Lovable @Replit - code generation AI companies" "analysis" "High GPU (40%+ costs)"

echo "================== MEDIUM GPU TEST =================="
echo "Testing search/synthesis companies (Perplexity, You.com)"
echo ""
test_format "Research @Perplexity @You.com - AI search companies" "analysis" "Medium GPU (25% costs)"

echo "================== LOW GPU TEST =================="
echo "Testing traditional SaaS with light AI (Ramp, Mercury)"
echo ""
test_format "Compare @Ramp @Mercury - fintech with AI features" "analysis" "Low GPU (10% costs)"

echo "================== MATRIX FORMAT TEST =================="
test_format "Compare @Cursor @Perplexity @Ramp for investor presentation" "matrix" "Matrix Format"

echo "================== DECK FORMAT TEST =================="
test_format "Create investor deck for @Gamma @Lovable @Cursor" "deck" "Deck Format"

echo "================== SPREADSHEET FORMAT TEST =================="
test_format "Build financial model for @Perplexity @You.com @Phind" "spreadsheet" "Spreadsheet Format"

echo ""
echo "✨ Tests completed!"
echo ""
echo "Expected GPU Cost Spectrum:"
echo "  1. Gamma/Lovable: $5-20 per code generation, 40% margin impact"
echo "  2. Perplexity: $0.10-0.50 per query, 25% margin impact"
echo "  3. Ramp/Mercury: $0.01-0.05 per API call, 10-15% margin impact"