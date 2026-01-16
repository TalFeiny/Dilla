#!/bin/bash

# Lago Self-Hosting Setup Script for Dilla AI
# This script sets up Lago billing without any Stripe dependencies

set -e

echo "🚀 Setting up Lago Self-Hosted Billing System"
echo "============================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
        echo "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Prerequisites satisfied${NC}"
}

# Generate secure keys
generate_keys() {
    echo -e "${YELLOW}Generating secure keys...${NC}"
    
    # Generate random passwords and keys
    LAGO_DB_PASSWORD=$(openssl rand -base64 32)
    LAGO_SECRET_KEY=$(openssl rand -base64 64)
    LAGO_ENCRYPTION_PRIMARY_KEY=$(openssl rand -base64 32 | head -c 32)
    LAGO_ENCRYPTION_DETERMINISTIC_KEY=$(openssl rand -base64 32 | head -c 32)
    LAGO_ENCRYPTION_KEY_DERIVATION_SALT=$(openssl rand -base64 32 | head -c 32)
    LAGO_API_KEY=$(openssl rand -base64 32)
    LAGO_WEBHOOK_SECRET=$(openssl rand -base64 32)
    
    # Generate RSA private key
    LAGO_RSA_PRIVATE_KEY=$(openssl genrsa 2048 2>/dev/null | base64 -w 0)
    
    echo -e "${GREEN}✓ Keys generated${NC}"
}

# Create .env.lago file
create_env_file() {
    echo -e "${YELLOW}Creating environment file...${NC}"
    
    cat > .env.lago <<EOF
# Lago Self-Hosted Configuration
# Generated on $(date)

# Database
LAGO_DB_PASSWORD=${LAGO_DB_PASSWORD}

# Security Keys
LAGO_SECRET_KEY=${LAGO_SECRET_KEY}
LAGO_ENCRYPTION_PRIMARY_KEY=${LAGO_ENCRYPTION_PRIMARY_KEY}
LAGO_ENCRYPTION_DETERMINISTIC_KEY=${LAGO_ENCRYPTION_DETERMINISTIC_KEY}
LAGO_ENCRYPTION_KEY_DERIVATION_SALT=${LAGO_ENCRYPTION_KEY_DERIVATION_SALT}
LAGO_RSA_PRIVATE_KEY=${LAGO_RSA_PRIVATE_KEY}

# API Configuration
LAGO_API_KEY=${LAGO_API_KEY}
LAGO_API_URL=http://localhost:3000/api/v1
LAGO_WEBHOOK_SECRET=${LAGO_WEBHOOK_SECRET}

# Email Settings (optional)
LAGO_FROM_EMAIL=billing@dilla.ai
LAGO_REPLY_TO_EMAIL=support@dilla.ai

# Environment
ENVIRONMENT=production
EOF

    echo -e "${GREEN}✓ Environment file created: .env.lago${NC}"
}

# Setup Lago with Docker
setup_lago_docker() {
    echo -e "${YELLOW}Setting up Lago with Docker...${NC}"
    
    # Clone Lago repository
    if [ ! -d "lago" ]; then
        echo "Cloning Lago repository..."
        git clone https://github.com/getlago/lago.git
    else
        echo "Lago repository already exists, pulling latest changes..."
        cd lago && git pull && cd ..
    fi
    
    # Use our custom docker-compose file
    echo "Starting Lago services..."
    docker-compose -f docker-compose.lago.yml --env-file .env.lago up -d
    
    echo -e "${GREEN}✓ Lago services started${NC}"
}

# Wait for services to be ready
wait_for_services() {
    echo -e "${YELLOW}Waiting for services to be ready...${NC}"
    
    # Wait for API to be ready
    echo -n "Waiting for Lago API..."
    for i in {1..30}; do
        if curl -s http://localhost:3000/health > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for UI to be ready
    echo -n "Waiting for Lago UI..."
    for i in {1..30}; do
        if curl -s http://localhost:80 > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
}

# Initialize Lago
initialize_lago() {
    echo -e "${YELLOW}Initializing Lago...${NC}"
    
    # Create organization via API
    echo "Creating organization..."
    curl -X POST http://localhost:3000/api/v1/organizations \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LAGO_API_KEY}" \
        -d '{
            "organization": {
                "name": "Dilla AI",
                "country": "US",
                "default_currency": "USD",
                "email": "billing@dilla.ai",
                "legal_name": "Dilla AI Inc",
                "tax_identification_number": "00-0000000",
                "timezone": "America/New_York"
            }
        }' > /dev/null 2>&1 || true
    
    # Create billable metrics
    echo "Creating billable metrics..."
    
    # Credit usage metric
    curl -X POST http://localhost:3000/api/v1/billable_metrics \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LAGO_API_KEY}" \
        -d '{
            "billable_metric": {
                "name": "API Credits",
                "code": "credit_usage",
                "description": "Credits consumed for API calls",
                "aggregation_type": "sum_agg",
                "field_name": "credits",
                "recurring": false
            }
        }' > /dev/null 2>&1 || true
    
    # Model cost metric (internal)
    curl -X POST http://localhost:3000/api/v1/billable_metrics \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LAGO_API_KEY}" \
        -d '{
            "billable_metric": {
                "name": "Model Costs",
                "code": "model_cost",
                "description": "Internal tracking of model API costs",
                "aggregation_type": "sum_agg",
                "field_name": "cost_usd",
                "recurring": false
            }
        }' > /dev/null 2>&1 || true
    
    echo -e "${GREEN}✓ Lago initialized${NC}"
}

# Create pricing plans
create_plans() {
    echo -e "${YELLOW}Creating pricing plans...${NC}"
    
    # Free Trial Plan
    curl -X POST http://localhost:3000/api/v1/plans \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LAGO_API_KEY}" \
        -d '{
            "plan": {
                "name": "Free Trial",
                "code": "free_trial",
                "interval": "monthly",
                "amount_cents": 0,
                "amount_currency": "USD",
                "trial_period": 0,
                "pay_in_advance": false,
                "charges": [{
                    "billable_metric_id": "credit_usage",
                    "charge_model": "package",
                    "properties": {
                        "amount": "0",
                        "free_units": 5,
                        "package_size": 1
                    }
                }]
            }
        }' > /dev/null 2>&1 || true
    
    # Starter Plan
    curl -X POST http://localhost:3000/api/v1/plans \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LAGO_API_KEY}" \
        -d '{
            "plan": {
                "name": "Starter",
                "code": "starter",
                "interval": "monthly",
                "amount_cents": 1900,
                "amount_currency": "USD",
                "trial_period": 7,
                "pay_in_advance": true,
                "charges": [{
                    "billable_metric_id": "credit_usage",
                    "charge_model": "package",
                    "properties": {
                        "amount": "150",
                        "free_units": 20,
                        "package_size": 1
                    }
                }]
            }
        }' > /dev/null 2>&1 || true
    
    echo -e "${GREEN}✓ Pricing plans created${NC}"
}

# Update application .env
update_app_env() {
    echo -e "${YELLOW}Updating application environment...${NC}"
    
    # Append Lago configuration to main .env if it exists
    if [ -f ".env" ]; then
        echo "" >> .env
        echo "# Lago Billing Configuration" >> .env
        echo "LAGO_API_KEY=${LAGO_API_KEY}" >> .env
        echo "LAGO_API_URL=http://localhost:3000/api/v1" >> .env
        echo "LAGO_WEBHOOK_SECRET=${LAGO_WEBHOOK_SECRET}" >> .env
        echo -e "${GREEN}✓ Main .env updated${NC}"
    else
        echo -e "${YELLOW}No .env file found, creating one...${NC}"
        cp .env.example .env 2>/dev/null || touch .env
        echo "" >> .env
        echo "# Lago Billing Configuration" >> .env
        echo "LAGO_API_KEY=${LAGO_API_KEY}" >> .env
        echo "LAGO_API_URL=http://localhost:3000/api/v1" >> .env
        echo "LAGO_WEBHOOK_SECRET=${LAGO_WEBHOOK_SECRET}" >> .env
        echo -e "${GREEN}✓ .env file created with Lago config${NC}"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${GREEN}🎉 Lago Setup Complete!${NC}"
    echo "========================"
    echo ""
    echo "Services Running:"
    echo "  • Lago API:     http://localhost:3000"
    echo "  • Lago UI:      http://localhost:80"
    echo "  • PostgreSQL:   localhost:5432"
    echo "  • Redis:        localhost:6379"
    echo ""
    echo "API Credentials:"
    echo "  • API Key: ${LAGO_API_KEY}"
    echo "  • API URL: http://localhost:3000/api/v1"
    echo ""
    echo "Next Steps:"
    echo "  1. Visit Lago UI at http://localhost:80"
    echo "  2. Configure webhook URL in Lago: http://localhost:8000/api/billing/webhook"
    echo "  3. Start your backend: cd backend && python3 -m uvicorn app.main:app --reload"
    echo "  4. Test the integration with a sample request"
    echo ""
    echo "Useful Commands:"
    echo "  • View logs:     docker-compose -f docker-compose.lago.yml logs -f"
    echo "  • Stop services: docker-compose -f docker-compose.lago.yml down"
    echo "  • Restart:       docker-compose -f docker-compose.lago.yml restart"
    echo ""
    echo -e "${YELLOW}⚠️  Important: Save your .env.lago file - it contains your keys!${NC}"
}

# Main execution
main() {
    echo ""
    check_prerequisites
    generate_keys
    create_env_file
    setup_lago_docker
    wait_for_services
    initialize_lago
    create_plans
    update_app_env
    print_summary
}

# Run main function
main