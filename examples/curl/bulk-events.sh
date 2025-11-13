#!/bin/bash
#
# Bulk Events Example
#
# Demonstrates sending multiple events with rate limiting and error handling.
#
# Usage:
#   export API_KEY="your-api-key"
#   ./bulk-events.sh [num_events]
#
# Example:
#   ./bulk-events.sh 10  # Send 10 events
#
# Requirements:
#   - curl (HTTP client)
#   - jq (JSON processor)
#

set -e

# Configuration
API_URL="${API_URL:-https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws}"
API_KEY="${API_KEY:-}"
NUM_EVENTS="${1:-5}"  # Default to 5 events
DELAY_BETWEEN_EVENTS=0.1  # 100ms delay (10 events/second)

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Counters
SUCCESS_COUNT=0
FAILURE_COUNT=0

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check prerequisites
if [ -z "$API_KEY" ]; then
    print_error "API_KEY environment variable is not set."
    echo "Usage: export API_KEY=\"your-key\" && $0 [num_events]"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    print_error "jq is not installed. Please install jq."
    exit 1
fi

# Authenticate
print_step "Authenticating..."
TOKEN_RESPONSE=$(curl -s -X POST "$API_URL/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=api&password=$API_KEY")

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    print_error "Authentication failed"
    echo "$TOKEN_RESPONSE" | jq '.'
    exit 1
fi

print_success "Authenticated successfully"
echo ""

# Event types to rotate through
EVENT_TYPES=(
    "user.signup"
    "user.login"
    "order.placed"
    "payment.succeeded"
    "document.uploaded"
)

# Send events
echo "=========================================="
echo "  Sending $NUM_EVENTS events"
echo "  Rate: ~10 events/second"
echo "=========================================="
echo ""

START_TIME=$(date +%s)

for i in $(seq 1 $NUM_EVENTS); do
    # Rotate through event types
    EVENT_TYPE=${EVENT_TYPES[$((($i - 1) % ${#EVENT_TYPES[@]}))]}

    # Generate event data
    EVENT_DATA=$(cat <<EOF
{
    "type": "$EVENT_TYPE",
    "source": "bulk-events-example",
    "payload": {
        "batch_id": "batch-$(date +%s)",
        "event_number": $i,
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "data": {
            "id": "item-$i",
            "value": $((RANDOM % 1000))
        }
    }
}
EOF
    )

    # Send event
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/events" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$EVENT_DATA")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" -eq 201 ]; then
        EVENT_ID=$(echo "$BODY" | jq -r '.id')
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo -e "${GREEN}[$i/$NUM_EVENTS]${NC} Created $EVENT_TYPE: $EVENT_ID"
    else
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        echo -e "${RED}[$i/$NUM_EVENTS]${NC} Failed $EVENT_TYPE (HTTP $HTTP_CODE)"
        echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
    fi

    # Rate limiting delay (except for last event)
    if [ $i -lt $NUM_EVENTS ]; then
        sleep $DELAY_BETWEEN_EVENTS
    fi
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Summary
echo ""
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""
echo "  Total events: $NUM_EVENTS"
echo -e "  ${GREEN}Successful: $SUCCESS_COUNT${NC}"
echo -e "  ${RED}Failed: $FAILURE_COUNT${NC}"
echo "  Time elapsed: ${ELAPSED}s"
echo "  Average rate: $(echo "scale=2; $NUM_EVENTS / $ELAPSED" | bc) events/second"
echo ""

# Verify inbox
print_step "Checking inbox for created events..."
INBOX_RESPONSE=$(curl -s -X GET "$API_URL/inbox" \
    -H "Authorization: Bearer $TOKEN")

INBOX_COUNT=$(echo "$INBOX_RESPONSE" | jq '. | length')

echo "  Pending events in inbox: $INBOX_COUNT"
echo ""

if [ "$SUCCESS_COUNT" -eq "$NUM_EVENTS" ]; then
    echo -e "${GREEN}✓ All events created successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "  - View inbox: curl -H \"Authorization: Bearer \$TOKEN\" $API_URL/inbox | jq"
    echo "  - Start polling consumer: ./polling-consumer.sh"
else
    echo -e "${YELLOW}⚠ Some events failed. Check error messages above.${NC}"
fi

echo ""
