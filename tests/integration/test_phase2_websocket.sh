#!/bin/bash

# Phase 2 WebSocket Integration Tests
# Tests WebSocket service health and basic functionality

echo "======================================"
echo "Signalink WebSocket Service Tests"
echo "Phase 2: Real-Time Messaging"
echo "======================================"
echo ""

# Configuration
WS_URL="http://localhost:8001"
API_URL="http://localhost:8000/api/v1"

# Test counters
PASSED=0
FAILED=0
TOTAL=0

# Helper function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo ""
    echo "============================================"
    echo "Test: $test_name"
    echo "============================================"

    TOTAL=$((TOTAL + 1))

    if eval "$test_command"; then
        echo "[PASS] $test_name"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo "[FAIL] $test_name"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Test 1: WebSocket Service Health
test_websocket_health() {
    echo "Checking WebSocket service health..."
    RESPONSE=$(curl -s http://localhost:8001/health)
    echo "Response: $RESPONSE"

    if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
        if echo "$RESPONSE" | grep -q '"redis":"connected"'; then
            echo "[OK] WebSocket service is healthy and Redis is connected"
            return 0
        fi
    fi

    echo "[FAIL] WebSocket service is not healthy"
    return 1
}

# Test 2: WebSocket Service Info
test_websocket_info() {
    echo "Checking WebSocket service info..."
    RESPONSE=$(curl -s http://localhost:8001/)
    echo "Response: $RESPONSE"

    if echo "$RESPONSE" | grep -q '"status":"operational"'; then
        echo "[OK] WebSocket service is operational"
        return 0
    fi

    echo "[FAIL] WebSocket service info failed"
    return 1
}

# Test 3: WebSocket Stats Endpoint
test_websocket_stats() {
    echo "Checking WebSocket stats..."
    RESPONSE=$(curl -s http://localhost:8001/stats)
    echo "Response: $RESPONSE"

    if echo "$RESPONSE" | grep -q '"total_connections"'; then
        if echo "$RESPONSE" | grep -q '"unique_users_online"'; then
            echo "[OK] WebSocket stats endpoint works"
            return 0
        fi
    fi

    echo "[FAIL] WebSocket stats endpoint failed"
    return 1
}

# Test 4: API Service Still Works
test_api_service() {
    echo "Verifying API service still works..."
    RESPONSE=$(curl -s http://localhost:8000/health)
    echo "Response: $RESPONSE"

    if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
        echo "[OK] API service is healthy"
        return 0
    fi

    echo "[FAIL] API service is not healthy"
    return 1
}

# Test 5: Docker Services Running
test_docker_services() {
    echo "Checking Docker services..."

    if docker-compose ps | grep -q "signalink_websocket.*Up"; then
        echo "[OK] WebSocket container is running"
        if docker-compose ps | grep -q "signalink_redis.*Up.*healthy"; then
            echo "[OK] Redis container is running and healthy"
            return 0
        fi
    fi

    echo "[FAIL] Docker services check failed"
    return 1
}

# Run all tests
echo "Running Phase 2 WebSocket Service Tests..."
echo ""

run_test "WebSocket Service Health" "test_websocket_health"
run_test "WebSocket Service Info" "test_websocket_info"
run_test "WebSocket Stats Endpoint" "test_websocket_stats"
run_test "API Service Health" "test_api_service"
run_test "Docker Services Status" "test_docker_services"

# Print summary
echo ""
echo "======================================"
echo "TEST SUMMARY"
echo "======================================"
echo "[PASS] Tests Passed: $PASSED"
echo "[FAIL] Tests Failed: $FAILED"
echo "Total Tests: $TOTAL"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "======================================"
    echo "All Tests Completed Successfully!"
    echo "======================================"
    echo ""
    echo "Note: Full WebSocket integration tests (real-time messaging,"
    echo "typing indicators, presence tracking) require Python and are"
    echo "available in test_phase2_websocket.py"
    echo ""
    echo "To run full WebSocket tests:"
    echo "  python tests/integration/test_phase2_websocket.py"
    echo ""
    exit 0
else
    echo "======================================"
    echo "Some Tests Failed!"
    echo "======================================"
    exit 1
fi
