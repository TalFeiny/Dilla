#!/bin/bash

# Log Monitoring Script for Dilla AI
# Provides real-time monitoring of frontend and backend logs

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
LOG_DIR="${LOG_DIR:-./logs}"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
ERROR_LOG="${LOG_DIR}/backend_errors.log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   Dilla AI Log Monitor${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Log Directory: ${LOG_DIR}${NC}"
echo ""

# Function to monitor a specific log file
monitor_log() {
    local log_file=$1
    local service_name=$2
    local color=$3
    
    if [ -f "$log_file" ]; then
        echo -e "${color}=== ${service_name} Log (${log_file}) ===${NC}"
        tail -f "$log_file" | while read line; do
            echo -e "${color}[${service_name}]${NC} $line"
        done &
    else
        echo -e "${YELLOW}⚠ Warning: ${log_file} not found${NC}"
        echo -e "${YELLOW}   Waiting for log file to be created...${NC}"
        # Wait for file to be created
        while [ ! -f "$log_file" ]; do
            sleep 1
        done
        tail -f "$log_file" | while read line; do
            echo -e "${color}[${service_name}]${NC} $line"
        done &
    fi
}

# Function to show errors only
show_errors() {
    if [ -f "$ERROR_LOG" ]; then
        echo -e "${RED}=== Recent Errors ===${NC}"
        tail -20 "$ERROR_LOG"
        echo ""
        echo -e "${CYAN}Monitoring for new errors... (Ctrl+C to exit)${NC}"
        tail -f "$ERROR_LOG"
    else
        echo -e "${YELLOW}No error log found yet${NC}"
    fi
}

# Function to show all logs in one view
show_all_logs() {
    echo -e "${CYAN}Monitoring all logs (Ctrl+C to exit)${NC}"
    echo ""
    
    # Monitor backend log
    if [ -f "$BACKEND_LOG" ]; then
        tail -f "$BACKEND_LOG" | sed "s/^/${GREEN}[BACKEND]${NC} /" &
    fi
    
    # Monitor frontend log
    if [ -f "$FRONTEND_LOG" ]; then
        tail -f "$FRONTEND_LOG" | sed "s/^/${BLUE}[FRONTEND]${NC} /" &
    fi
    
    # Monitor error log
    if [ -f "$ERROR_LOG" ]; then
        tail -f "$ERROR_LOG" | sed "s/^/${RED}[ERROR]${NC} /" &
    fi
    
    # Wait for all background processes
    wait
}

# Function to show log statistics
show_stats() {
    echo -e "${CYAN}=== Log Statistics ===${NC}"
    echo ""
    
    if [ -f "$BACKEND_LOG" ]; then
        backend_lines=$(wc -l < "$BACKEND_LOG")
        backend_size=$(du -h "$BACKEND_LOG" | cut -f1)
        echo -e "${GREEN}Backend Log:${NC} $backend_lines lines, $backend_size"
    fi
    
    if [ -f "$FRONTEND_LOG" ]; then
        frontend_lines=$(wc -l < "$FRONTEND_LOG")
        frontend_size=$(du -h "$FRONTEND_LOG" | cut -f1)
        echo -e "${BLUE}Frontend Log:${NC} $frontend_lines lines, $frontend_size"
    fi
    
    if [ -f "$ERROR_LOG" ]; then
        error_lines=$(wc -l < "$ERROR_LOG")
        error_size=$(du -h "$ERROR_LOG" | cut -f1)
        echo -e "${RED}Error Log:${NC} $error_lines lines, $error_size"
    fi
    
    echo ""
    echo -e "${CYAN}Recent Errors (last 5):${NC}"
    if [ -f "$ERROR_LOG" ]; then
        tail -5 "$ERROR_LOG" | while read line; do
            echo -e "${RED}  $line${NC}"
        done
    else
        echo -e "${GREEN}  No errors found${NC}"
    fi
}

# Function to search logs
search_logs() {
    local search_term=$1
    echo -e "${CYAN}Searching logs for: ${search_term}${NC}"
    echo ""
    
    if [ -f "$BACKEND_LOG" ]; then
        echo -e "${GREEN}=== Backend Matches ===${NC}"
        grep -i "$search_term" "$BACKEND_LOG" | tail -20
    fi
    
    if [ -f "$FRONTEND_LOG" ]; then
        echo -e "${BLUE}=== Frontend Matches ===${NC}"
        grep -i "$search_term" "$FRONTEND_LOG" | tail -20
    fi
    
    if [ -f "$ERROR_LOG" ]; then
        echo -e "${RED}=== Error Log Matches ===${NC}"
        grep -i "$search_term" "$ERROR_LOG" | tail -20
    fi
}

# Main menu
case "${1:-all}" in
    backend)
        monitor_log "$BACKEND_LOG" "BACKEND" "$GREEN"
        wait
        ;;
    frontend)
        monitor_log "$FRONTEND_LOG" "FRONTEND" "$BLUE"
        wait
        ;;
    errors)
        show_errors
        ;;
    stats)
        show_stats
        ;;
    search)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please provide a search term${NC}"
            echo "Usage: $0 search <term>"
            exit 1
        fi
        search_logs "$2"
        ;;
    all)
        show_all_logs
        ;;
    *)
        echo -e "${CYAN}Usage: $0 [backend|frontend|errors|stats|all|search <term>]${NC}"
        echo ""
        echo "Commands:"
        echo "  backend   - Monitor backend logs only"
        echo "  frontend  - Monitor frontend logs only"
        echo "  errors    - Monitor error logs only"
        echo "  stats     - Show log statistics"
        echo "  search    - Search logs for a term"
        echo "  all       - Monitor all logs (default)"
        exit 1
        ;;
esac

