#!/bin/bash
#
# Basic API Flow Example
#
# Demonstrates the complete Zapier Triggers API workflow:
# 1. Authenticate and get JWT token
# 2. Create an event
# 3. Retrieve inbox
# 4. Acknowledge event delivery
#
# Usage:
#   export API_KEY="your-api-key"
#   ./basic-flow.sh
#
# Requirements:
#   - curl (HTTP client)
#   - jq (JSON processor)
#

set -e  # Exit on error

# Configuration
API_URL="${API_URL:-https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws}"
API_KEY="${API_KEY:-}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Helper functions
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

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."

    if ! command -v curl &> /dev/null; then
        print_error "curl is not installed. Please install curl."
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed. Please install jq (brew install jq or apt-get install jq)."
        exit 1
    fi

    if [ -z "$API_KEY" ]; then
        print_error "API_KEY environment variable is not set."
        echo ""
        echo "Please set your API key:"
        echo "  export API_KEY=\"your-api-key-here\""
        echo ""
        echo "To get your API key from AWS Secrets Manager:"
        echo "  aws secretsmanager get-secret-value \\"
        echo "    --secret-id zapier-api-credentials-{stackName} \\"
        echo "    --region us-east-2 \\"
        echo "    --query SecretString --output text | jq -r '.zapier_api_key'"
        exit 1
    fi

    print_success "Prerequisites met"
    echo ""
}

# Step 1: Authenticate
authenticate() {
    print_step "Step 1: Authenticating with API..."
    echo "  URL: $API_URL/token"
    echo "  Username: api"
    echo ""

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=api&password=$API_KEY")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "Authentication failed (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        exit 1
    fi

    TOKEN=$(echo "$body" | jq -r '.access_token')

    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        print_error "Failed to extract token from response"
        echo "$body" | jq '.'
        exit 1
    fi

    print_success "Authentication successful"
    echo "  Token: ${TOKEN:0:20}...${TOKEN: -10}"
    echo ""
}

# Step 2: Create Event
create_event() {
    print_step "Step 2: Creating event..."

    local event_data='{
        "type": "user.signup",
        "source": "basic-flow-example",
        "payload": {
            "user_id": "demo-'$(date +%s)'",
            "email": "demo@example.com",
            "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
        }
    }'

    echo "  Event data:"
    echo "$event_data" | jq '.'

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/events" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$event_data")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 201 ]; then
        print_error "Event creation failed (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        exit 1
    fi

    EVENT_ID=$(echo "$body" | jq -r '.id')
    EVENT_STATUS=$(echo "$body" | jq -r '.status')

    print_success "Event created successfully"
    echo "  Event ID: $EVENT_ID"
    echo "  Status: $EVENT_STATUS"
    echo "  Response:"
    echo "$body" | jq '.'
    echo ""
}

# Step 3: Retrieve Inbox
get_inbox() {
    print_step "Step 3: Retrieving inbox..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X GET "$API_URL/inbox" \
        -H "Authorization: Bearer $TOKEN")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "Inbox retrieval failed (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        exit 1
    fi

    local event_count=$(echo "$body" | jq '. | length')

    print_success "Inbox retrieved successfully"
    echo "  Pending events: $event_count"

    if [ "$event_count" -gt 0 ]; then
        echo "  Events:"
        echo "$body" | jq '.[] | {id: .id, type: .type, status: .status, created_at: .created_at}'
    else
        print_warning "Inbox is empty"
    fi

    echo ""
}

# Step 4: Acknowledge Event
acknowledge_event() {
    if [ -z "$EVENT_ID" ]; then
        print_warning "No event ID available to acknowledge"
        return
    fi

    print_step "Step 4: Acknowledging event delivery..."
    echo "  Event ID: $EVENT_ID"

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/inbox/$EVENT_ID/ack" \
        -H "Authorization: Bearer $TOKEN")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "Event acknowledgment failed (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        exit 1
    fi

    print_success "Event acknowledged successfully"
    echo "  Response:"
    echo "$body" | jq '.'
    echo ""
}

# Step 5: Verify Empty Inbox
verify_empty_inbox() {
    print_step "Step 5: Verifying event removed from inbox..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X GET "$API_URL/inbox" \
        -H "Authorization: Bearer $TOKEN")

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        print_error "Inbox verification failed (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        exit 1
    fi

    local event_count=$(echo "$body" | jq '. | length')
    local our_event_present=$(echo "$body" | jq --arg id "$EVENT_ID" '[.[] | select(.id == $id)] | length')

    print_success "Inbox verification complete"
    echo "  Total pending events: $event_count"

    if [ "$our_event_present" -eq 0 ]; then
        print_success "Our event ($EVENT_ID) has been removed from inbox"
    else
        print_warning "Our event ($EVENT_ID) is still in inbox"
    fi

    echo ""
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  Zapier Triggers API - Basic Flow"
    echo "=========================================="
    echo ""
    echo "API URL: $API_URL"
    echo ""

    check_prerequisites
    authenticate
    create_event
    get_inbox
    acknowledge_event
    verify_empty_inbox

    echo "=========================================="
    echo -e "${GREEN}✓ Workflow completed successfully!${NC}"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  - View API documentation: $API_URL/docs"
    echo "  - Read developer guide: ../docs/DEVELOPER_GUIDE.md"
    echo "  - Try bulk events: ./bulk-events.sh"
    echo ""
}

# Run main function
main
