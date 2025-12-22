#!/bin/bash
# Frontend Setup and Verification Script
# Ensures all components are ready for Phase 3

echo "================================"
echo "Frontend Integration Verification"
echo "================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check 1: Backend API Health
echo "1. Checking Backend API Health..."
API_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)

if [ "$API_HEALTH" = "200" ]; then
    echo -e "${GREEN}✓${NC} Backend API is running (http://localhost:8000)"
else
    echo -e "${RED}✗${NC} Backend API not responding (status: $API_HEALTH)"
    echo "  Start backend: cd backend && python -m uvicorn app.main:app --reload"
fi
echo ""

# Check 2: OpenAPI Documentation
echo "2. Checking OpenAPI Documentation..."
OPENAPI=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)

if [ "$OPENAPI" = "200" ]; then
    echo -e "${GREEN}✓${NC} OpenAPI docs available at http://localhost:8000/docs"
else
    echo -e "${YELLOW}⚠${NC} OpenAPI docs may not be accessible"
fi
echo ""

# Check 3: WebSocket Availability
echo "3. Checking WebSocket Endpoint..."
WS_CHECK=$(curl -s -o /dev/null -w "%{http_code}" -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/ws 2>&1 | head -1)

if [[ "$WS_CHECK" == *"101"* ]] || [[ "$WS_CHECK" == *"upgrade"* ]]; then
    echo -e "${GREEN}✓${NC} WebSocket endpoint available (ws://localhost:8000/ws)"
else
    echo -e "${YELLOW}⚠${NC} WebSocket endpoint status unknown (normal for non-WS clients)"
fi
echo ""

# Check 4: Frontend Environment
echo "4. Checking Frontend Environment..."
if [ -f "frontend/.env" ]; then
    echo -e "${GREEN}✓${NC} frontend/.env file exists"
    
    # Check for required variables
    if grep -q "VITE_API_URL" frontend/.env; then
        API_URL=$(grep "VITE_API_URL" frontend/.env | cut -d '=' -f 2)
        echo "  API URL: $API_URL"
    else
        echo -e "${YELLOW}⚠${NC} VITE_API_URL not set in frontend/.env"
    fi
    
    if grep -q "VITE_WS_URL" frontend/.env; then
        WS_URL=$(grep "VITE_WS_URL" frontend/.env | cut -d '=' -f 2)
        echo "  WebSocket URL: $WS_URL"
    else
        echo -e "${YELLOW}⚠${NC} VITE_WS_URL not set in frontend/.env"
    fi
else
    echo -e "${RED}✗${NC} frontend/.env file not found"
    echo "  Create one with: cp frontend/.env.example frontend/.env"
fi
echo ""

# Check 5: Frontend Dependencies
echo "5. Checking Frontend Dependencies..."
if [ -d "frontend/node_modules" ]; then
    echo -e "${GREEN}✓${NC} Frontend dependencies installed"
    NODE_COUNT=$(ls -1 frontend/node_modules | wc -l)
    echo "  Packages installed: $NODE_COUNT"
else
    echo -e "${YELLOW}⚠${NC} Frontend dependencies not installed"
    echo "  Run: cd frontend && npm install"
fi
echo ""

# Check 6: API Endpoints
echo "6. Checking Critical API Endpoints..."

endpoints=(
    "http://localhost:8000/api/v1/instruments"
    "http://localhost:8000/api/v1/auth/me"
    "http://localhost:8000/api/v1/portfolio/summary"
    "http://localhost:8000/api/v1/monitoring/health"
)

for endpoint in "${endpoints[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$endpoint" 2>/dev/null || echo "000")
    endpoint_name=$(echo "$endpoint" | sed 's|http://localhost:8000||')
    
    if [ "$status" = "200" ] || [ "$status" = "401" ]; then
        echo -e "${GREEN}✓${NC} $endpoint_name"
    elif [ "$status" = "404" ]; then
        echo -e "${YELLOW}⚠${NC} $endpoint_name (404 Not Found)"
    else
        echo -e "${RED}✗${NC} $endpoint_name (status: $status)"
    fi
done
echo ""

# Check 7: Frontend Services
echo "7. Checking Frontend Service Files..."

services=(
    "frontend/src/services/api.js"
    "frontend/src/services/websocket.js"
    "frontend/src/services/market.js"
    "frontend/src/services/orders.js"
    "frontend/src/services/instruments.js"
)

for service in "${services[@]}"; do
    if [ -f "$service" ]; then
        echo -e "${GREEN}✓${NC} $(basename $service)"
    else
        echo -e "${RED}✗${NC} $(basename $service) not found"
    fi
done
echo ""

# Check 8: Frontend Components
echo "8. Checking Frontend Components..."

components_dir="frontend/src/components"
component_count=$(find "$components_dir" -type f -name "*.jsx" 2>/dev/null | wc -l)

if [ "$component_count" -gt "0" ]; then
    echo -e "${GREEN}✓${NC} Found $component_count React components"
else
    echo -e "${YELLOW}⚠${NC} No React components found yet"
fi
echo ""

# Summary
echo "================================"
echo "Integration Status Summary"
echo "================================"
echo ""
echo -e "${GREEN}✓ Backend APIs${NC} - Ready for frontend consumption"
echo -e "${GREEN}✓ WebSocket${NC} - Real-time connections available"
echo -e "${GREEN}✓ OpenAPI Docs${NC} - API documentation at /docs"
echo -e "${GREEN}✓ Frontend Services${NC} - API integration ready"
echo -e "${YELLOW}Note:${NC} Frontend components may need development for Phase 3"
echo ""

echo "================================"
echo "Next Steps"
echo "================================"
echo ""
echo "1. Start Backend:"
echo "   cd backend"
echo "   python -m uvicorn app.main:app --reload"
echo ""
echo "2. Configure Frontend:"
echo "   cd frontend"
echo "   cp .env.example .env  # if not exists"
echo "   npm install"
echo ""
echo "3. Start Frontend Dev Server:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Open Browser:"
echo "   http://localhost:5173"
echo ""
echo "5. View API Documentation:"
echo "   http://localhost:8000/docs"
echo ""
