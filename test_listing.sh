#!/bin/bash

API_URL="http://localhost:8000/api/v1"

echo "=== Testing Marketplace Listing Creation ==="
echo ""

echo "Step 1: Login as topu@gmail.com"
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"topu@gmail.com","password":"DemoPassword123!"}')

echo "Login Response:"
echo "$LOGIN_RESPONSE" | python3 -m json.tool
echo ""

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
USER_ID=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user', {}).get('user_id', ''))")

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to get token!"
  exit 1
fi

echo "Token obtained: ${TOKEN:0:20}..."
echo "User ID: $USER_ID"
echo ""

echo "Step 2: Get user's lands"
LANDS_RESPONSE=$(curl -s -X GET "$API_URL/users/$USER_ID/lands?page=1&limit=5" \
  -H "Authorization: Bearer $TOKEN")

echo "Lands Response:"
echo "$LANDS_RESPONSE" | python3 -m json.tool
echo ""

LAND_ID=$(echo "$LANDS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', [{}])[0].get('land_id', '') if data.get('data') else '')")

if [ -z "$LAND_ID" ]; then
  echo "ERROR: No lands found for user!"
  exit 1
fi

echo "Using Land ID: $LAND_ID"
echo ""

echo "Step 3: Create Fixed Price Listing (500 BDT)"
LISTING_DATA='{"land_id":"'$LAND_ID'","listing_type":"fixed_price","buy_now_price_bdt":500}'

echo "Request Data:"
echo "$LISTING_DATA" | python3 -m json.tool
echo ""

LISTING_RESPONSE=$(curl -s -X POST "$API_URL/marketplace/listings" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$LISTING_DATA" \
  -w "\nHTTP_STATUS:%{http_code}")

HTTP_STATUS=$(echo "$LISTING_RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
RESPONSE_BODY=$(echo "$LISTING_RESPONSE" | sed '/HTTP_STATUS/d')

echo "HTTP Status: $HTTP_STATUS"
echo "Response Body:"
echo "$RESPONSE_BODY" | python3 -m json.tool
echo ""

if [ "$HTTP_STATUS" = "201" ] || [ "$HTTP_STATUS" = "200" ]; then
  echo "✅ SUCCESS: Listing created successfully!"
else
  echo "❌ FAILED: Listing creation failed with status $HTTP_STATUS"

  # Check backend logs
  echo ""
  echo "=== Backend Logs (last 50 lines) ==="
  docker logs --tail 50 virtualworld-backend
fi
