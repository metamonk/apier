#!/bin/bash
#
# Polling Consumer Example
#
# Implements a continuous polling loop to consume events from the inbox.
# Similar to how Zapier polls the API for new events.
#
# Usage:
#   export API_KEY="your-api-key"
#   ./polling-consumer.sh
#
# Press Ctrl+C to stop.
#
# Requirements:
#   - curl (HTTP client)
#   - jq (JSON processor)
#

# Configuration
API_URL="${API_URL:-https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws}"
API_KEY="${API_KEY:-}"
POLL_INTERVAL=10  # Poll every 10 seconds

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Counters
TOTAL_PROCESSED=0
TOTAL_ERRORS=0

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Signal handler for graceful shutdown
cleanup() {
    echo ""
    echo ""
    echo "=========================================="
    echo "  Polling stopped (Ctrl+C)"
    echo "=========================================="
    echo ""
    echo "  Total events processed: $TOTAL_PROCESSED"
    echo "  Total errors: $TOTAL_ERRORS"
    echo ""
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check prerequisites
if [ -z "$API_KEY" ]; then
    print_error "API_KEY environment variable is not set."
    echo "Usage: export API_KEY=\"your-key\" && $0"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    print_error "jq is not installed. Please install jq."
    exit 1
fi

# Authenticate
authenticate() {
    print_step "Authenticating..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=api&password=$API_KEY")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "Authentication failed (HTTP $http_code)"
        echo "$body" | jq '.'
        exit 1
    fi

    TOKEN=$(echo "$body" | jq -r '.access_token')

    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        print_error "Failed to extract token"
        exit 1
    fi

    print_success "Authenticated successfully"
}

# Process a single event
process_event() {
    local event=$1
    local event_id=$(echo "$event" | jq -r '.id')
    local event_type=$(echo "$event" | jq -r '.type')
    local event_source=$(echo "$event" | jq -r '.source')

    echo ""
    print_step "Processing event: $event_id"
    echo "  Type: $event_type"
    echo "  Source: $event_source"

    # Simulate event processing
    echo "  Payload:"
    echo "$event" | jq '.payload'

    # Simulate work (0.5-2 seconds)
    local work_time=$(echo "scale=1; $(($RANDOM % 15 + 5)) / 10" | bc)
    echo "  Processing... (${work_time}s)"
    sleep $work_time

    # Acknowledge event
    local ack_response
    ack_response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/inbox/$event_id/ack" \
        -H "Authorization: Bearer $TOKEN")

    local ack_code=$(echo "$ack_response" | tail -n1)

    if [ "$ack_code" -eq 200 ]; then
        print_success "Event acknowledged: $event_id"
        TOTAL_PROCESSED=$((TOTAL_PROCESSED + 1))
    else
        print_error "Failed to acknowledge event: $event_id (HTTP $ack_code)"
        TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
    fi
}

# Poll inbox
poll_inbox() {
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo ""
    echo "[$timestamp] Polling inbox..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X GET "$API_URL/inbox" \
        -H "Authorization: Bearer $TOKEN")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "Inbox poll failed (HTTP $http_code)"

        # Check if token expired (401)
        if [ "$http_code" -eq 401 ]; then
            print_warning "Token expired, re-authenticating..."
            authenticate
        fi

        return
    fi

    local event_count=$(echo "$body" | jq '. | length')

    if [ "$event_count" -eq 0 ]; then
        echo "  No pending events"
        echo "  Waiting ${POLL_INTERVAL}s for next poll..."
    else
        print_success "Found $event_count pending event(s)"

        # Process each event
        echo "$body" | jq -c '.[]' | while read -r event; do
            process_event "$event"
        done

        echo ""
        echo "  Processed $event_count event(s)"
        echo "  Total processed: $TOTAL_PROCESSED"
    fi
}

# Main polling loop
main() {
    echo ""
    echo "=========================================="
    echo "  Zapier Triggers API - Polling Consumer"
    echo "=========================================="
    echo ""
    echo "  API URL: $API_URL"
    echo "  Poll interval: ${POLL_INTERVAL}s"
    echo ""
    echo "  Press Ctrl+C to stop"
    echo "=========================================="

    # Initial authentication
    authenticate

    echo ""
    echo "Starting polling loop..."

    # Polling loop
    while true; do
        poll_inbox
        sleep $POLL_INTERVAL
    done
}

# Run main function
main
