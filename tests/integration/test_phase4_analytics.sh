#!/bin/bash

# Phase 4 Analytics Infrastructure Test Suite
# Tests analytics service infrastructure and dependencies

set -e

ANALYTICS_URL="http://localhost:8002"
API_URL="http://localhost:8000"
KAFKA_BOOTSTRAP_EXTERNAL="localhost:9093"
KAFKA_BOOTSTRAP_INTERNAL="localhost:9092"

echo "========================================"
echo "Phase 4: Analytics Infrastructure Tests"
echo "========================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

# Test function
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

# 1. Test Analytics Service is Running
echo "1. Analytics Service Health"
echo "----------------------------"

test_case "Analytics service is accessible" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL | grep -q '200\|404'"

test_case "Analytics health endpoint responds" \
    "curl -s $ANALYTICS_URL/health | grep -q 'status'"

test_case "Analytics root endpoint responds" \
    "curl -s $ANALYTICS_URL/ | grep -q 'Signalink'"

echo ""

# 2. Test Database Connectivity
echo "2. Database Schema"
echo "-------------------"

test_case "message_metrics table exists" \
    "docker exec signalink_db psql -U signalink -d signalink -c '\dt message_metrics' | grep -q 'message_metrics'"

test_case "channel_metrics table exists" \
    "docker exec signalink_db psql -U signalink -d signalink -c '\dt channel_metrics' | grep -q 'channel_metrics'"

test_case "user_metrics table exists" \
    "docker exec signalink_db psql -U signalink -d signalink -c '\dt user_metrics' | grep -q 'user_metrics'"

echo ""

# 3. Test Kafka Consumer Connection
echo "3. Kafka Consumer"
echo "------------------"

test_case "Analytics consumer group exists" \
    "timeout 15 docker exec signalink_kafka kafka-consumer-groups --bootstrap-server $KAFKA_BOOTSTRAP_INTERNAL --list | grep -q 'analytics-consumers'"

# Give the consumer a moment to subscribe
# Retry mechanism to handle transient Kafka rebalancing
echo -n "Testing: Analytics consumer subscribed to messages topic... "
for attempt in {1..10}; do
    if timeout 10 docker exec signalink_kafka kafka-consumer-groups --bootstrap-server $KAFKA_BOOTSTRAP_INTERNAL --describe --group analytics-consumers 2>/dev/null | grep -q 'signalink.messages'; then
        echo -e "${GREEN}[PASS]${NC}"
        ((pass_count++)) || true
        break
    fi

    if [ $attempt -eq 10 ]; then
        echo -e "${RED}[FAIL]${NC}"
        ((fail_count++)) || true
    else
        sleep 2
    fi
done

echo ""

# 4. Test Analytics API Endpoints
echo "4. Analytics API Endpoints"
echo "---------------------------"

test_case "GET /metrics/messages endpoint exists" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL/metrics/messages | grep -q '200'"

test_case "GET /metrics/system/stats endpoint exists" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL/metrics/system/stats | grep -q '200'"

test_case "GET /metrics/channels/top/active endpoint exists" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL/metrics/channels/top/active | grep -q '200'"

test_case "GET /metrics/users/top/active endpoint exists" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL/metrics/users/top/active | grep -q '200'"

test_case "GET /metrics/system/timeseries endpoint exists" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL/metrics/system/timeseries | grep -q '200'"

echo ""

# 5. Test API Documentation
echo "5. API Documentation"
echo "---------------------"

test_case "OpenAPI schema is available" \
    "curl -s $ANALYTICS_URL/openapi.json | grep -q 'openapi'"

test_case "Swagger UI is accessible" \
    "curl -s -o /dev/null -w '%{http_code}' $ANALYTICS_URL/docs | grep -q '200'"

echo ""

# Summary
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Passed: ${GREEN}$pass_count${NC}"
echo -e "Failed: ${RED}$fail_count${NC}"
echo "Total:  $((pass_count + fail_count))"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✓ All infrastructure tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please check the output above.${NC}"
    exit 1
fi
