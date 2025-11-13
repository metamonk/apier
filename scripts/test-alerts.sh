#!/bin/bash

# CloudWatch Alerts Testing Script
# Tests the alerting system by triggering different alarm scenarios

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="${AWS_REGION:-us-east-2}"
FUNCTION_URL="${FUNCTION_URL:-}"
STACK_NAME="${STACK_NAME:-}"

# Functions
print_header() {
    echo -e "\n${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    print_success "AWS CLI is installed"
}

# Get Function URL from CloudFormation
get_function_url() {
    if [ -z "$FUNCTION_URL" ]; then
        print_info "Fetching Lambda Function URL from CloudFormation..."

        if [ -z "$STACK_NAME" ]; then
            # Try to find the stack name
            STACK_NAME=$(aws cloudformation list-stacks \
                --region $REGION \
                --query "StackSummaries[?contains(StackName, 'amplify-apier') && StackStatus=='CREATE_COMPLETE'].StackName" \
                --output text | head -n 1)
        fi

        if [ -z "$STACK_NAME" ]; then
            print_error "Could not find CloudFormation stack. Please set STACK_NAME or FUNCTION_URL environment variable."
            exit 1
        fi

        FUNCTION_URL=$(aws cloudformation describe-stacks \
            --stack-name $STACK_NAME \
            --region $REGION \
            --query "Stacks[0].Outputs[?OutputKey=='TriggersApiUrl'].OutputValue" \
            --output text)

        if [ -z "$FUNCTION_URL" ]; then
            print_error "Could not retrieve Function URL from stack: $STACK_NAME"
            exit 1
        fi

        print_success "Function URL: $FUNCTION_URL"
    fi
}

# Get alarm names
get_alarm_names() {
    if [ -z "$STACK_NAME" ]; then
        STACK_NAME=$(aws cloudformation list-stacks \
            --region $REGION \
            --query "StackSummaries[?contains(StackName, 'amplify-apier') && StackStatus=='CREATE_COMPLETE'].StackName" \
            --output text | head -n 1)
    fi

    ERROR_ALARM="zapier-api-high-errors-$(echo $STACK_NAME | cut -d'-' -f3-)"
    DURATION_ALARM="zapier-api-high-duration-$(echo $STACK_NAME | cut -d'-' -f3-)"
    THROTTLE_ALARM="zapier-api-throttling-$(echo $STACK_NAME | cut -d'-' -f3-)"
    DYNAMO_ALARM="zapier-api-dynamo-read-throttle-$(echo $STACK_NAME | cut -d'-' -f3-)"
}

# Test 1: Trigger High Error Rate Alarm
test_error_rate() {
    print_header "Test 1: High Error Rate Alarm"
    print_info "Sending 15 invalid requests to trigger error alarm (threshold: 10 errors)"
    print_warning "This will take ~2-3 minutes. Alarm evaluation: 5-10 minutes."

    get_function_url

    echo ""
    for i in {1..15}; do
        echo -n "Sending request $i/15..."
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$FUNCTION_URL/events" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer invalid_token_12345" \
            -d '{"type": "test.error", "source": "test", "payload": {}}' 2>&1)

        if [ "$RESPONSE" == "401" ] || [ "$RESPONSE" == "403" ]; then
            echo -e " ${GREEN}✓ Error generated (HTTP $RESPONSE)${NC}"
        else
            echo -e " ${RED}✗ Unexpected response (HTTP $RESPONSE)${NC}"
        fi

        sleep 0.5
    done

    echo ""
    print_success "Completed sending error requests"
    print_info "Monitor alarm status:"
    print_info "  aws cloudwatch describe-alarms --alarm-names $ERROR_ALARM --region $REGION"
    print_warning "Alarm will trigger in 5-10 minutes if threshold is exceeded"
    print_info "Check your email/SMS for notification"
}

# Test 2: Trigger Throttling Alarm
test_throttling() {
    print_header "Test 2: Throttling Alarm"
    print_info "Sending 500 concurrent requests to potentially exceed Lambda concurrency"
    print_warning "This may impact production traffic. Use with caution!"

    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Test cancelled"
        return
    fi

    get_function_url

    echo ""
    print_info "Launching 500 concurrent requests..."

    for i in {1..500}; do
        curl -s -o /dev/null "$FUNCTION_URL/health" &
    done
    wait

    print_success "Completed sending concurrent requests"
    print_info "Monitor alarm status:"
    print_info "  aws cloudwatch describe-alarms --alarm-names $THROTTLE_ALARM --region $REGION"
    print_warning "Alarm will trigger in 1-2 minutes if throttling occurred"
}

# Test 3: Manual Alarm Trigger (Safest)
test_manual_trigger() {
    print_header "Test 3: Manual Alarm Trigger"
    print_info "This is the safest way to test notifications without impacting the system"

    get_alarm_names

    echo -e "\nAvailable alarms:"
    echo "  1. $ERROR_ALARM"
    echo "  2. $DURATION_ALARM"
    echo "  3. $THROTTLE_ALARM"
    echo "  4. $DYNAMO_ALARM"
    echo ""

    read -p "Select alarm to trigger (1-4): " choice

    case $choice in
        1)
            ALARM_NAME=$ERROR_ALARM
            ;;
        2)
            ALARM_NAME=$DURATION_ALARM
            ;;
        3)
            ALARM_NAME=$THROTTLE_ALARM
            ;;
        4)
            ALARM_NAME=$DYNAMO_ALARM
            ;;
        *)
            print_error "Invalid choice"
            return
            ;;
    esac

    print_info "Triggering alarm: $ALARM_NAME"

    aws cloudwatch set-alarm-state \
        --alarm-name "$ALARM_NAME" \
        --state-value ALARM \
        --state-reason "Testing alert notification system via test-alerts.sh" \
        --region $REGION

    if [ $? -eq 0 ]; then
        print_success "Alarm triggered successfully"
        print_info "Check your email/SMS for notification (should arrive within 1-2 minutes)"
        print_info "Alarm will auto-recover when actual metrics show OK state"

        echo ""
        print_info "To manually reset the alarm:"
        print_info "  aws cloudwatch set-alarm-state --alarm-name $ALARM_NAME --state-value OK --state-reason 'Manual reset' --region $REGION"
    else
        print_error "Failed to trigger alarm"
    fi
}

# Test 4: Check Alarm Status
test_check_status() {
    print_header "Test 4: Check Alarm Status"

    get_alarm_names

    echo -e "\n${BLUE}Current Alarm States:${NC}\n"

    aws cloudwatch describe-alarms \
        --alarm-names "$ERROR_ALARM" "$DURATION_ALARM" "$THROTTLE_ALARM" "$DYNAMO_ALARM" \
        --region $REGION \
        --query 'MetricAlarms[*].[AlarmName,StateValue,StateReason]' \
        --output table

    print_info "For detailed information, use:"
    print_info "  aws cloudwatch describe-alarms --alarm-names ALARM_NAME --region $REGION"
}

# Test 5: Verify SNS Subscriptions
test_check_subscriptions() {
    print_header "Test 5: Check SNS Subscriptions"

    if [ -z "$STACK_NAME" ]; then
        get_alarm_names
    fi

    print_info "Fetching SNS Topic ARN..."

    TOPIC_ARN=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query "Stacks[0].Outputs[?OutputKey=='AlertsTopicArn'].OutputValue" \
        --output text)

    if [ -z "$TOPIC_ARN" ]; then
        print_error "Could not retrieve SNS Topic ARN"
        return
    fi

    print_success "SNS Topic ARN: $TOPIC_ARN"

    echo -e "\n${BLUE}Subscriptions:${NC}\n"

    SUBS=$(aws sns list-subscriptions-by-topic \
        --topic-arn "$TOPIC_ARN" \
        --region $REGION \
        --query 'Subscriptions[*].[Protocol,Endpoint,SubscriptionArn]' \
        --output table)

    if [ -z "$SUBS" ]; then
        print_warning "No subscriptions found!"
        print_info "To subscribe to email notifications:"
        print_info "  aws sns subscribe --topic-arn $TOPIC_ARN --protocol email --notification-endpoint your@email.com --region $REGION"
    else
        echo "$SUBS"
    fi
}

# Display usage
usage() {
    echo "Usage: $0 [test-type]"
    echo ""
    echo "Test Types:"
    echo "  error-rate       - Trigger high error rate alarm (safe)"
    echo "  throttling       - Trigger throttling alarm (use with caution)"
    echo "  manual           - Manually set alarm state (safest)"
    echo "  status           - Check current alarm status"
    echo "  subscriptions    - Check SNS subscriptions"
    echo "  all              - Run all safe tests"
    echo ""
    echo "Environment Variables:"
    echo "  FUNCTION_URL     - Lambda Function URL (optional, auto-detected)"
    echo "  STACK_NAME       - CloudFormation stack name (optional, auto-detected)"
    echo "  AWS_REGION       - AWS region (default: us-east-2)"
    echo ""
    echo "Examples:"
    echo "  $0 manual"
    echo "  $0 status"
    echo "  FUNCTION_URL=https://... $0 error-rate"
}

# Main script
main() {
    print_header "CloudWatch Alerts Testing Script"

    check_aws_cli

    if [ $# -eq 0 ]; then
        usage
        exit 0
    fi

    case "$1" in
        error-rate)
            test_error_rate
            ;;
        throttling)
            test_throttling
            ;;
        manual)
            test_manual_trigger
            ;;
        status)
            test_check_status
            ;;
        subscriptions)
            test_check_subscriptions
            ;;
        all)
            test_check_status
            test_check_subscriptions
            test_error_rate
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown test type: $1"
            usage
            exit 1
            ;;
    esac

    echo ""
    print_success "Test completed!"
    print_info "See docs/SNS_ALERTS.md for more information"
}

main "$@"
