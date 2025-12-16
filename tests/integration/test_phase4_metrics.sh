#!/bin/bash

# Phase 4 Metrics Aggregation Test Suite
# Tests real-time metrics calculation and aggregation

set -e

ANALYTICS_URL="http://localhost:8002"
API_URL="http://localhost:8000/api/v1"

echo "============================================"
echo "Phase 4: Metrics Aggregation Tests"
echo "============================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass_count=0
fail_count=0

test_case() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}[PASS]${NC}"
        ((pass_count++)) || true
        return 0
    else
        echo -e "${RED}[FAIL]${NC}"
        ((fail_count++)) || true
        return 1
    fi
}

# Get auth token
echo "Obtaining authentication token..."
AUTH_RESPONSE=$(curl -s -X POST "$API_URL/users/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"testpass123"}')

TOKEN=$(echo $AUTH_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo -e "${YELLOW}Warning: Could not get auth token. Creating test user...${NC}"

    # Register test user
    curl -s -X POST "$API_URL/users/register" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }' > /dev/null 2>&1

    # Login again
    AUTH_RESPONSE=$(curl -s -X POST "$API_URL/users/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"testuser","password":"testpass123"}')

    TOKEN=$(echo $AUTH_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
fi

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Failed to obtain authentication token${NC}"
    exit 1
fi

echo -e "${GREEN}Token obtained successfully${NC}"
echo ""

# Get or create a test channel
echo "Setting up test channel..."

# Always create a new channel to ensure user is the owner
CHANNEL_CREATE=$(curl -s -X POST "$API_URL/channels/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "analytics-test-'$(date +%s)'",
        "description": "Channel for analytics testing",
        "is_private": false
    }')

CHANNEL_ID=$(echo $CHANNEL_CREATE | grep -o '"id":"[^"]*' | cut -d'"' -f4)

if [ -z "$CHANNEL_ID" ]; then
    echo -e "${RED}Failed to create test channel${NC}"
    exit 1
fi

echo "Created channel ID: $CHANNEL_ID"
echo ""

# 1. Test Message Event Generation
echo "1. Message Event Generation"
echo "----------------------------"

echo "Sending test messages..."
for i in {1..5}; do
    curl -s -X POST "$API_URL/messages/" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"channel_id\": \"$CHANNEL_ID\",
            \"content\": \"Analytics test message $i\",
            \"message_type\": \"text\"
        }" > /dev/null

    echo -n "."
    sleep 0.5
done

echo ""
echo "Sent 5 test messages"
echo ""

# Wait for metrics aggregation (one window cycle)
echo "Waiting for metrics aggregation (65 seconds for window flush)..."
sleep 65

echo ""

# 2. Test Message Metrics
echo "2. Message Metrics Aggregation"
echo "--------------------------------"

METRICS_RESPONSE=$(curl -s "$ANALYTICS_URL/metrics/messages?hours=1&limit=10")

test_case "Message metrics contain data" \
    "echo '$METRICS_RESPONSE' | grep -q 'time_window'"

test_case "Message count is recorded" \
    "echo '$METRICS_RESPONSE' | grep -q 'message_count'"

test_case "Messages per second calculated" \
    "echo '$METRICS_RESPONSE' | grep -q 'messages_per_second'"

test_case "Active users count tracked" \
    "echo '$METRICS_RESPONSE' | grep -q 'active_users_count'"

test_case "Message type breakdown available" \
    "echo '$METRICS_RESPONSE' | grep -q 'text_messages_count'"

echo ""

# 3. Test Channel Metrics
echo "3. Channel Metrics"
echo "-------------------"

CHANNEL_METRICS=$(curl -s "$ANALYTICS_URL/metrics/channels/$CHANNEL_ID?hours=1&limit=10")

test_case "Channel metrics contain data" \
    "echo '$CHANNEL_METRICS' | grep -q 'channel_id'"

test_case "Channel message count recorded" \
    "echo '$CHANNEL_METRICS' | grep -q 'message_count'"

test_case "Channel unique senders tracked" \
    "echo '$CHANNEL_METRICS' | grep -q 'unique_senders_count'"

test_case "Channel created count tracked" \
    "echo '$CHANNEL_METRICS' | grep -q 'created_count'"

echo ""

# 4. Test System Statistics
echo "4. System Statistics"
echo "---------------------"

SYSTEM_STATS=$(curl -s "$ANALYTICS_URL/metrics/system/stats?hours=1")

test_case "System stats return total messages" \
    "echo '$SYSTEM_STATS' | grep -q 'total_messages_last_hour'"

test_case "System stats calculate messages per second" \
    "echo '$SYSTEM_STATS' | grep -q 'messages_per_second'"

test_case "System stats track active users" \
    "echo '$SYSTEM_STATS' | grep -q 'active_users_last_hour'"

test_case "System stats track active channels" \
    "echo '$SYSTEM_STATS' | grep -q 'active_channels_last_hour'"

echo ""

# 5. Test Top Active Resources
echo "5. Top Active Resources"
echo "------------------------"

TOP_CHANNELS=$(curl -s "$ANALYTICS_URL/metrics/channels/top/active?hours=1&limit=5")
TOP_USERS=$(curl -s "$ANALYTICS_URL/metrics/users/top/active?hours=1&limit=5")

test_case "Top active channels endpoint works" \
    "echo '$TOP_CHANNELS' | grep -q '\['"

test_case "Top active users endpoint works" \
    "echo '$TOP_USERS' | grep -q '\['"

echo ""

# 6. Test Time Series Data
echo "6. Time Series Data"
echo "--------------------"

TIMESERIES=$(curl -s "$ANALYTICS_URL/metrics/system/timeseries?hours=2&interval_minutes=60")

test_case "Time series data available" \
    "echo '$TIMESERIES' | grep -q '\['"

test_case "Time series contains timestamp" \
    "echo '$TIMESERIES' | grep -q 'timestamp'"

test_case "Time series contains message_count" \
    "echo '$TIMESERIES' | grep -q 'message_count'"

echo ""

# 7. Test Database Persistence
echo "7. Database Persistence"
echo "------------------------"

test_case "message_metrics table has data" \
    "docker exec signalink_db psql -U signalink -d signalink -t -c 'SELECT COUNT(*) FROM message_metrics' | grep -q -v '^[[:space:]]*0'"

test_case "channel_metrics table has data" \
    "docker exec signalink_db psql -U signalink -d signalink -t -c 'SELECT COUNT(*) FROM channel_metrics' | grep -q -v '^[[:space:]]*0'"

echo ""

# Summary
echo "============================================"
echo "Test Summary"
echo "============================================"
echo -e "Passed: ${GREEN}$pass_count${NC}"
echo -e "Failed: ${RED}$fail_count${NC}"
echo "Total:  $((pass_count + fail_count))"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✓ All metrics aggregation tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please check the output above.${NC}"
    exit 1
fi
