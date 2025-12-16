#!/bin/bash

# Phase 4 Complete Integration Test Suite
# Runs all Phase 4 analytics tests in sequence

set -e

echo "================================================"
echo "Phase 4: Complete Analytics Integration Tests"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

total_pass=0
total_fail=0
test_suite_count=0

# Function to run a test suite
run_test_suite() {
    local suite_name="$1"
    local script_path="$2"

    echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Running: $suite_name${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ -f "$script_path" ]; then
        if bash "$script_path"; then
            echo -e "${GREEN}✓ $suite_name completed successfully${NC}"
            ((test_suite_count++)) || true
        else
            echo -e "${RED}✗ $suite_name failed${NC}"
            ((total_fail++)) || true
            return 1
        fi
    else
        echo -e "${RED}✗ Test script not found: $script_path${NC}"
        ((total_fail++)) || true
        return 1
    fi

    echo ""
    echo ""
}

# Check if required services are running
echo "Checking required services..."
echo "------------------------------"

ANALYTICS_URL="http://localhost:8002"
API_URL="http://localhost:8000"

if ! curl -s -o /dev/null "$API_URL/health" 2>/dev/null; then
    echo -e "${RED}Error: API service is not running at $API_URL${NC}"
    echo "Please start services with: docker-compose --profile phase2 --profile phase3 --profile phase4 up -d"
    exit 1
fi

if ! curl -s -o /dev/null "$ANALYTICS_URL/health" 2>/dev/null; then
    echo -e "${RED}Error: Analytics service is not running at $ANALYTICS_URL${NC}"
    echo "Please start services with: docker-compose --profile phase2 --profile phase3 --profile phase4 up -d"
    exit 1
fi

echo -e "${GREEN}✓ All required services are running${NC}"
echo ""
echo ""

# Run test suites in sequence
run_test_suite "Analytics Infrastructure Tests" "$SCRIPT_DIR/test_phase4_analytics.sh"
run_test_suite "Metrics Aggregation Tests" "$SCRIPT_DIR/test_phase4_metrics.sh"

# Final Summary
echo "================================================"
echo "Phase 4 Test Execution Summary"
echo "================================================"
echo ""
echo "Test Suites Executed: $test_suite_count"
echo ""

if [ $total_fail -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║   ✓ ALL PHASE 4 TESTS PASSED SUCCESSFULLY!    ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Phase 4 - Analytics Microservice is complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review metrics in Swagger UI: http://localhost:8002/docs"
    echo "  2. Query analytics data via API endpoints"
    echo "  3. Monitor Kafka consumer lag: docker exec signalink_kafka kafka-consumer-groups --bootstrap-server localhost:9093 --describe --group analytics-consumers"
    echo "  4. Proceed to Phase 5: Notification System"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                ║${NC}"
    echo -e "${RED}║          ✗ SOME TESTS FAILED                   ║${NC}"
    echo -e "${RED}║                                                ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Failed test suites: $total_fail"
    echo ""
    echo "Please review the test output above and fix any failing tests."
    exit 1
fi
