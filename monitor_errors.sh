#!/bin/bash

# Monitor errors in both frontend and backend logs

echo "=== Monitoring Backend and Frontend Errors ==="
echo ""
echo "Press Ctrl+C to stop monitoring"
echo ""

# Tail both log files and highlight errors
tail -f backend.log frontend.log 2>/dev/null | grep --line-buffered -E "(ERROR|WARN|error|Error|Exception|Failed|failed|✗|⚠)" --color=always

