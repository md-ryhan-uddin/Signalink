#!/bin/bash

API_URL="http://localhost:8000/api/v1"

echo "=========================================="
echo "Phase 3 Complete Integration Test"
echo "Kafka Producer + Consumer + All Events"
echo "=========================================="

# Create user
TIMESTAMP=$(date +%s)
USERNAME="phase3_test_$TIMESTAMP"

echo -e "\n1. Creating test user..."
REG_RESPONSE=$(curl -s -X POST "$API_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"email\":\"phase3_$TIMESTAMP@test.com\",\"password\":\"Test123!@#\",\"full_name\":\"Phase 3 Test\"}")

# Login
echo -e "\n2. Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"Test123!@#\"}")

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "[FAIL] Failed to login"
    exit 1
fi

echo "[OK] Login successful"

# Create a channel
echo -e "\n3. Creating test channel..."
CHANNEL_RESPONSE=$(curl -s -X POST "$API_URL/channels/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"name\":\"phase3_test_$TIMESTAMP\",\"description\":\"Phase 3 test channel\",\"is_private\":false}")

CHANNEL_ID=$(echo $CHANNEL_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$CHANNEL_ID" ]; then
    echo "[FAIL] Failed to create channel"
    exit 1
fi

echo "[OK] Channel created: $CHANNEL_ID"

# Test 1: Create Message Event
echo -e "\n=========================================="
echo "TEST 1: message.created Event"
echo "=========================================="

MSG_RESPONSE=$(curl -s -X POST "$API_URL/messages/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"channel_id\":\"$CHANNEL_ID\",\"content\":\"Original message content\",\"message_type\":\"text\"}")

MESSAGE_ID=$(echo $MSG_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$MESSAGE_ID" ]; then
    echo "[FAIL] Failed to send message"
    exit 1
fi

echo "[OK] Message created: $MESSAGE_ID"
sleep 2

# Verify producer published message.created
if docker logs signalink_api 2>&1 | grep -q "Published message.created event for message $MESSAGE_ID"; then
    echo "[OK] Producer published message.created event"
else
    echo "[FAIL] Producer did not publish message.created event"
    exit 1
fi

# Verify consumer processed message.created
if docker logs signalink_api 2>&1 | grep -q "Processing message.created event: message_id=$MESSAGE_ID"; then
    echo "[OK] Consumer processed message.created event"
else
    echo "[FAIL] Consumer did not process message.created event"
    exit 1
fi

# Test 2: Update Message Event
echo -e "\n=========================================="
echo "TEST 2: message.edited Event"
echo "=========================================="

UPDATE_RESPONSE=$(curl -s -X PUT "$API_URL/messages/$MESSAGE_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"content\":\"Updated message content\"}")

if echo "$UPDATE_RESPONSE" | grep -q "is_edited"; then
    echo "[OK] Message updated successfully"
else
    echo "[FAIL] Failed to update message"
    exit 1
fi

sleep 2

# Verify producer published message.edited
if docker logs signalink_api 2>&1 | grep -q "Published message.edited event for message $MESSAGE_ID"; then
    echo "[OK] Producer published message.edited event"
else
    echo "[FAIL] Producer did not publish message.edited event"
    exit 1
fi

# Verify consumer processed message.edited
if docker logs signalink_api 2>&1 | grep -q "Processing message.edited event: message_id=$MESSAGE_ID"; then
    echo "[OK] Consumer processed message.edited event"
else
    echo "[FAIL] Consumer did not process message.edited event"
    exit 1
fi

# Test 3: Delete Message Event
echo -e "\n=========================================="
echo "TEST 3: message.deleted Event"
echo "=========================================="

DELETE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$API_URL/messages/$MESSAGE_ID" \
  -H "Authorization: Bearer $TOKEN")

if [ "$DELETE_RESPONSE" = "204" ]; then
    echo "[OK] Message deleted successfully (HTTP 204)"
else
    echo "[FAIL] Failed to delete message (HTTP $DELETE_RESPONSE)"
    exit 1
fi

sleep 2

# Verify producer published message.deleted
if docker logs signalink_api 2>&1 | grep -q "Published message.deleted event for message $MESSAGE_ID"; then
    echo "[OK] Producer published message.deleted event"
else
    echo "[FAIL] Producer did not publish message.deleted event"
    exit 1
fi

# Verify consumer processed message.deleted
if docker logs signalink_api 2>&1 | grep -q "Processing message.deleted event: message_id=$MESSAGE_ID"; then
    echo "[OK] Consumer processed message.deleted event"
else
    echo "[FAIL] Consumer did not process message.deleted event"
    exit 1
fi

# Test 4: Verify Consumer Group Health
echo -e "\n=========================================="
echo "TEST 4: Consumer Group Health"
echo "=========================================="

CONSUMER_GROUP=$(docker exec signalink_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group signalink-consumers \
  --describe 2>&1)

# Check all 4 topics are being consumed
TOPICS_COUNT=$(echo "$CONSUMER_GROUP" | grep -c "signalink\.")

if [ "$TOPICS_COUNT" -ge 4 ]; then
    echo "[OK] Consumer group consuming from all 4 topics"
    echo "$CONSUMER_GROUP" | grep "signalink\." | awk '{printf "    %-25s LAG: %s\n", $2, $6}'
else
    echo "[FAIL] Consumer group not consuming from all topics (found $TOPICS_COUNT/4)"
    exit 1
fi

# Test 5: Check Kafka Topics
echo -e "\n=========================================="
echo "TEST 5: Kafka Topics Configuration"
echo "=========================================="

TOPICS=$(docker exec signalink_kafka kafka-topics --bootstrap-server localhost:9092 --list 2>&1)

EXPECTED_TOPICS=("signalink.messages" "signalink.notifications" "signalink.analytics" "signalink.presence")
ALL_TOPICS_EXIST=true

for topic in "${EXPECTED_TOPICS[@]}"; do
    if echo "$TOPICS" | grep -q "^$topic$"; then
        echo "[OK] Topic exists: $topic"
    else
        echo "[FAIL] Topic missing: $topic"
        ALL_TOPICS_EXIST=false
    fi
done

if [ "$ALL_TOPICS_EXIST" = false ]; then
    exit 1
fi

# Final Summary
echo -e "\n=========================================="
echo "[PASS] All Phase 3 Tests Passed!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Kafka Producer Integration"
echo "  ✓ Kafka Consumer Integration"
echo "  ✓ message.created event flow"
echo "  ✓ message.edited event flow"
echo "  ✓ message.deleted event flow"
echo "  ✓ Consumer group health check"
echo "  ✓ All 4 topics configured correctly"
echo ""
echo "Event Processing Pipeline:"
echo "  1. API Endpoint → Database"
echo "  2. Kafka Producer → Kafka Topic"
echo "  3. Kafka Consumer → Event Handler"
echo "  4. Handler logs confirmation"
echo ""
echo "Phase 3 (Kafka Event Streaming) Complete!"
echo ""
