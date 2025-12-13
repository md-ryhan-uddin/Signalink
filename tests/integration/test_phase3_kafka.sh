#!/bin/bash

API_URL="http://localhost:8000/api/v1"

echo "=========================================="
echo "Kafka Integration Test - Phase 3"
echo "=========================================="

# Create user
TIMESTAMP=$(date +%s)
USERNAME="kafka_test_$TIMESTAMP"

echo -e "\n1. Creating test user..."
REG_RESPONSE=$(curl -s -X POST "$API_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"email\":\"kafka_$TIMESTAMP@test.com\",\"password\":\"Test123!@#\",\"full_name\":\"Kafka Test\"}")

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
  -d "{\"name\":\"kafka_test_$TIMESTAMP\",\"description\":\"Kafka test channel\",\"is_private\":false}")

CHANNEL_ID=$(echo $CHANNEL_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$CHANNEL_ID" ]; then
    echo "[FAIL] Failed to create channel"
    exit 1
fi

echo "[OK] Channel created: $CHANNEL_ID"

# Send a message
echo -e "\n4. Sending a message..."
MSG_RESPONSE=$(curl -s -X POST "$API_URL/messages/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"channel_id\":\"$CHANNEL_ID\",\"content\":\"Test Kafka message at $(date +%s)\",\"message_type\":\"text\"}")

MESSAGE_ID=$(echo $MSG_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$MESSAGE_ID" ]; then
    echo "[FAIL] Failed to send message"
    echo "Response: $MSG_RESPONSE"
    exit 1
fi

echo "[OK] Message sent successfully: $MESSAGE_ID"

# Wait a moment for Kafka
sleep 2

# Check Kafka topic exists
echo -e "\n5. Checking Kafka topics..."
TOPICS=$(docker exec signalink_kafka kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null)

if echo "$TOPICS" | grep -q "signalink.messages"; then
    echo "[OK] Kafka topic 'signalink.messages' exists"
else
    echo "[FAIL] Kafka topic 'signalink.messages' not found"
    exit 1
fi

# Check API logs for Kafka publish
echo -e "\n6. Checking API logs for Kafka publish..."
KAFKA_LOGS=$(docker logs signalink_api 2>&1 | grep "Published message.created" | tail -3)

if [ -n "$KAFKA_LOGS" ]; then
    echo "[OK] Kafka events being published:"
    echo "$KAFKA_LOGS"
else
    echo "[FAIL] No Kafka publish logs found"
    exit 1
fi

# Check Kafka broker
echo -e "\n7. Checking Kafka broker..."
if docker exec signalink_kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1 | grep -q "kafka-signalink:9092"; then
    echo "[OK] Kafka broker is responsive"
else
    echo "[FAIL] Kafka broker not responding"
    exit 1
fi

echo -e "\n=========================================="
echo "[PASS] All Kafka Integration Tests Passed!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - API connected to Kafka successfully"
echo "  - Messages being published to Kafka topic"
echo "  - Topic 'signalink.messages' created automatically"
echo "  - Kafka broker healthy and responsive"
echo ""
echo "Next steps:"
echo "  - Implement Kafka consumer service"
echo "  - Test end-to-end event flow"
