#!/bin/bash

# Signalink API Testing Script
# Tests all Phase 1 endpoints

echo "======================================"
echo "Signalink API Comprehensive Test"
echo "======================================"
echo ""

BASE_URL="http://localhost:8000"

# Test 1: Health Check
echo "1. Testing Health Endpoint..."
HEALTH=$(curl -s "$BASE_URL/health")
echo "$HEALTH" | python -m json.tool
echo ""

# Test 2: Root Endpoint
echo "2. Testing Root Endpoint..."
ROOT=$(curl -s "$BASE_URL/")
echo "$ROOT" | python -m json.tool
echo ""

# Test 3: User Registration
echo "3. Testing User Registration..."
TIMESTAMP=$(date +%s)
TEST_USER="testuser_$TIMESTAMP"
REGISTER=$(curl -s -X POST "$BASE_URL/api/v1/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$TEST_USER\", \"email\": \"test_$TIMESTAMP@signalink.com\", \"password\": \"testpass123\", \"full_name\": \"Test User\"}")
echo "$REGISTER" | python -m json.tool
echo ""

# Test 4: User Login
echo "4. Testing User Login..."
LOGIN=$(curl -s -X POST "$BASE_URL/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$TEST_USER\", \"password\": \"testpass123\"}")
echo "$LOGIN" | python -m json.tool

TOKEN=$(echo "$LOGIN" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
echo "Token: ${TOKEN:0:50}..."
echo ""

# Test 5: Get Current User Profile
echo "5. Testing Get Current User..."
PROFILE=$(curl -s -X GET "$BASE_URL/api/v1/users/me" \
  -H "Authorization: Bearer $TOKEN")
echo "$PROFILE" | python -m json.tool
echo ""

# Test 6: Create Channel
echo "6. Testing Create Channel..."
CHANNEL_NAME="channel_$TIMESTAMP"
CHANNEL=$(curl -s -X POST "$BASE_URL/api/v1/channels/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$CHANNEL_NAME\", \"description\": \"Test channel\", \"is_private\": false}")
echo "$CHANNEL" | python -m json.tool

CHANNEL_ID=$(echo "$CHANNEL" | python -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "Channel ID: $CHANNEL_ID"
echo ""

# Test 7: List Channels
echo "7. Testing List Channels..."
CHANNELS=$(curl -s -X GET "$BASE_URL/api/v1/channels/" \
  -H "Authorization: Bearer $TOKEN")
echo "$CHANNELS" | python -m json.tool
echo ""

# Test 8: Send Message
echo "8. Testing Send Message..."
MESSAGE=$(curl -s -X POST "$BASE_URL/api/v1/messages/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"channel_id\": \"$CHANNEL_ID\", \"content\": \"Hello, Signalink!\", \"message_type\": \"text\"}")
echo "$MESSAGE" | python -m json.tool

MESSAGE_ID=$(echo "$MESSAGE" | python -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "Message ID: $MESSAGE_ID"
echo ""

# Test 9: Get Channel Messages
echo "9. Testing Get Channel Messages..."
MESSAGES=$(curl -s -X GET "$BASE_URL/api/v1/messages/channels/$CHANNEL_ID" \
  -H "Authorization: Bearer $TOKEN")
echo "$MESSAGES" | python -m json.tool
echo ""

# Test 10: Search Users
echo "10. Testing Search Users..."
USERS=$(curl -s -X GET "$BASE_URL/api/v1/users/?query=test" \
  -H "Authorization: Bearer $TOKEN")
echo "$USERS" | python -m json.tool
echo ""

echo "======================================"
echo "✅ All Tests Completed!"
echo "======================================"
