#!/bin/bash
# Seraph AI Defense System - Deployment Validation Script
# =======================================================
# Run this after docker-compose up to verify all services

set -e

echo "=================================================="
echo "  Seraph AI - Deployment Validation"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://165.22.41.184:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://165.22.41.184:3000}"
API_BASE_URL="${API_BASE_URL:-${BACKEND_BASE_URL}/api}"

BACKEND_BASE_URL="${BACKEND_BASE_URL%/}"
FRONTEND_URL="${FRONTEND_URL%/}"
API_BASE_URL="${API_BASE_URL%/}"

if [[ "$API_BASE_URL" =~ /api$ ]]; then
    BACKEND_BASE_URL="${API_BASE_URL%/api}"
fi

check_service() {
    local service=$1
    local check_cmd=$2
    
    if eval "$check_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $service"
        return 0
    else
        echo -e "${RED}✗${NC} $service"
        return 1
    fi
}

# Check Docker services
echo "Checking Docker Services..."
echo "-------------------------------------------"

check_service "MongoDB" "docker exec seraph-mongodb mongosh --eval 'db.adminCommand(\"ping\")' 2>/dev/null"
check_service "Backend" "curl -sf ${API_BASE_URL}/health"
check_service "Frontend" "curl -sf ${FRONTEND_URL}"
check_service "WireGuard" "docker exec seraph-wireguard wg show 2>/dev/null || docker ps | grep seraph-wireguard"

echo ""
echo "Checking Backend Features..."
echo "-------------------------------------------"

# Get auth token
RESPONSE=$(curl -sf -X POST "${API_BASE_URL}/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"test-deploy@seraph.ai","password":"TestDeploy123!","name":"Test"}' 2>/dev/null || \
    curl -sf -X POST "${API_BASE_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test-deploy@seraph.ai","password":"TestDeploy123!"}')

TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓${NC} Authentication"
    
    # Test protected endpoints
    check_service "CLI Sessions API" "curl -sf ${API_BASE_URL}/cli/sessions/all -H 'Authorization: Bearer $TOKEN'"
    check_service "SOAR API" "curl -sf ${API_BASE_URL}/soar/stats -H 'Authorization: Bearer $TOKEN'"
    check_service "VPN API" "curl -sf ${API_BASE_URL}/vpn/status -H 'Authorization: Bearer $TOKEN'"
    check_service "Zero Trust API" "curl -sf ${API_BASE_URL}/zero-trust/stats -H 'Authorization: Bearer $TOKEN'"
else
    echo -e "${YELLOW}⚠${NC} Authentication - Could not get token"
fi

echo ""
echo "Checking CCE Worker..."
echo "-------------------------------------------"
if docker logs seraph-backend 2>&1 | grep -q "CCE Worker started"; then
    echo -e "${GREEN}✓${NC} CCE Worker Running"
else
    echo -e "${YELLOW}⚠${NC} CCE Worker - Check logs"
fi

echo ""
echo "=================================================="
echo "  Deployment Summary"
echo "=================================================="
echo ""
echo "Access Points:"
echo "  🖥️  Web UI:    ${FRONTEND_URL}"
echo "  🔌 API:       ${API_BASE_URL}"
echo "  🔐 VPN:       localhost:51820/udp"
echo ""
echo "Next Steps:"
echo "  1. Open ${FRONTEND_URL} and register an account"
echo "  2. Configure notifications in Settings"
echo "  3. Deploy agents to endpoints"
echo "  4. Set up VPN for secure agent communication"
echo ""
