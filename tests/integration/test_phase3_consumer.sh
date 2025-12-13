#!/bin/bash

API_URL="http://localhost:8000/api/v1"

echo "=========================================="
echo "Kafka Consumer Test - Phase 3"
echo "=========================================="

# Create user
TIMESTAMP=$(date +%s)
USERNAME="consumer_test_$TIMESTAMP"

echo -e "\n1. Creating test user..."
REG_RESPONSE=$(curl -s -X POST "$API_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"email\":\"consumer_$TIMESTAMP@test.com\",\"password\":\"Test123!@#\",\"full_name\":\"Consumer Test\"}")

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
  -d "{\"name\":\"consumer_test_$TIMESTAMP\",\"description\":\"Consumer test channel\",\"is_private\":false}")

CHANNEL_ID=$(echo $CHANNEL_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$CHANNEL_ID" ]; then
    echo "[FAIL] Failed to create channel"
    exit 1
fi

echo "[OK] Channel created: $CHANNEL_ID"

# Clear logs before sending message
echo -e "\n4. Preparing to send message..."
BEFORE_TIME=$(date +%s)
sleep 1

# Send a message
echo -e "\n5. Sending a message..."
MSG_CONTENT="End-to-end test message at $(date +%s)"
MSG_RESPONSE=$(curl -s -X POST "$API_URL/messages/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"channel_id\":\"$CHANNEL_ID\",\"content\":\"$MSG_CONTENT\",\"message_type\":\"text\"}")

MESSAGE_ID=$(echo $MSG_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$MESSAGE_ID" ]; then
    echo "[FAIL] Failed to send message"
    echo "Response: $MSG_RESPONSE"
    exit 1
fi

echo "[OK] Message sent successfully: $MESSAGE_ID"

# Wait for Kafka consumer to process
echo -e "\n6. Waiting for consumer to process event..."
sleep 3

# Check producer logs
echo -e "\n7. Verifying producer published event..."
PRODUCER_LOG=$(docker logs signalink_api 2>&1 | grep "Published message.created event for message $MESSAGE_ID")

if [ -n "$PRODUCER_LOG" ]; then
    echo "[OK] Producer published event:"
    echo "    $PRODUCER_LOG"
else
    echo "[FAIL] Producer did not publish event"
    exit 1
fi

# Check consumer logs
echo -e "\n8. Verifying consumer processed event..."
CONSUMER_LOG=$(docker logs signalink_api 2>&1 | grep "Processing message.created event: message_id=$MESSAGE_ID")

if [ -n "$CONSUMER_LOG" ]; then
    echo "[OK] Consumer processed event:"
    echo "    $CONSUMER_LOG"
else
    echo "[FAIL] Consumer did not process event"
    echo "Checking all consumer logs:"
    docker logs signalink_api 2>&1 | grep "Processing message.created" | tail -5
    exit 1
fi

# Verify event data integrity
echo -e "\n9. Verifying event data integrity..."
if echo "$CONSUMER_LOG" | grep -q "channel_id=$CHANNEL_ID"; then
    echo "[OK] Channel ID matches in consumer event"
else
    echo "[FAIL] Channel ID mismatch in consumer event"
    exit 1
fi

# Check Kafka consumer group status
echo -e "\n10. Checking Kafka consumer group status..."
if docker exec signalink_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group signalink-consumers \
  --describe 2>&1 | grep -q "signalink.messages"; then
    echo "[OK] Consumer group is active for signalink.messages topic"
    # Show lag
    LAG_INFO=$(docker exec signalink_kafka kafka-consumer-groups \
      --bootstrap-server localhost:9092 \
      --group signalink-consumers \
      --describe 2>&1 | grep "signalink.messages")
    MESSAGES_LAG=$(echo "$LAG_INFO" | awk '{print $6}')
    echo "    Current lag: $MESSAGES_LAG messages"
else
    echo "[FAIL] Consumer group not found for signalink.messages topic"
    exit 1
fi

echo -e "\n=========================================="
echo "[PASS] All Kafka Consumer Tests Passed!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Message created via API: $MESSAGE_ID"
echo "  - Producer published event to Kafka ✓"
echo "  - Consumer received and processed event ✓"
echo "  - Event data integrity verified ✓"
echo "  - Consumer group active and healthy ✓"
echo ""
echo "End-to-End Event Flow:"
echo "  API → Kafka Producer → Kafka Topic → Kafka Consumer → Event Handler"
echo ""
