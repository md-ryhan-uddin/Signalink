#!/bin/bash
API_URL="http://localhost:8000/api/v1"
TIMESTAMP=$(date +%s)
USERNAME="debug_$TIMESTAMP"

# Register
curl -s -X POST "$API_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"email\":\"debug_$TIMESTAMP@test.com\",\"password\":\"Test123!@#\",\"full_name\":\"Debug\"}" > /dev/null

# Login
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"Test123!@#\"}")

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# Create channel
CHANNEL_RESPONSE=$(curl -s -X POST "$API_URL/channels/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"name\":\"debug_$TIMESTAMP\",\"description\":\"Debug\",\"is_private\":false}")

CHANNEL_ID=$(echo $CHANNEL_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

# Create message
MSG_RESPONSE=$(curl -s -X POST "$API_URL/messages/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"channel_id\":\"$CHANNEL_ID\",\"content\":\"Debug message\",\"message_type\":\"text\"}")

MESSAGE_ID=$(echo $MSG_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

echo "Created message: $MESSAGE_ID"

sleep 2

# Edit message
curl -s -X PUT "$API_URL/messages/$MESSAGE_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"content\":\"Debug edited\"}" > /dev/null

echo "Edited message: $MESSAGE_ID"

sleep 2

# Check logs
echo "Checking logs for message $MESSAGE_ID:"
docker logs signalink_api 2>&1 | grep "$MESSAGE_ID"
