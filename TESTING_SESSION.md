# Development Environment Testing Session

## Environment Details

**Development URLs:**
- Frontend: https://dev.dmmfqlsr845yz.amplifyapp.com
- Backend API: https://jahwrrz53a6hsqjyf5j3cerfcq0jwpaj.lambda-url.us-east-2.on.aws
- API Key: `UP5v3CKgjhXFdvYwg/rRpzMdxfbBhSbXe2mVm4BALOY=`

## Quick Start Testing

```bash
# Set environment variables
export API_URL="https://jahwrrz53a6hsqjyf5j3cerfcq0jwpaj.lambda-url.us-east-2.on.aws"
export API_KEY="UP5v3CKgjhXFdvYwg/rRpzMdxfbBhSbXe2mVm4BALOY="

# Get JWT token
export TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=api" \
  --data-urlencode "password=$API_KEY" \
  | jq -r '.access_token')

echo "Token: ${TOKEN:0:50}..."
```

## Test Checklist

### ✅ 1. API Backend Tests

#### Health Check
```bash
curl -s "$API_URL/health" | jq
# Expected: {"status": "healthy"}
```

#### Authentication
```bash
curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=api" \
  --data-urlencode "password=$API_KEY" \
  | jq
# Expected: JWT token response
```

#### Create Event
```bash
curl -s -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "user.signup",
    "source": "manual-test",
    "payload": {
      "user_id": "test_123",
      "email": "test@example.com",
      "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
    }
  }' | jq
```

#### Get Inbox
```bash
curl -s "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### Get Event Summary
```bash
curl -s "$API_URL/events/summary" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### List Events
```bash
curl -s "$API_URL/events?status=pending&limit=10" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### Get Specific Event
```bash
# First, get an event ID from the inbox
EVENT_ID=$(curl -s "$API_URL/inbox" -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

curl -s "$API_URL/events/$EVENT_ID" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### Acknowledge Event
```bash
curl -s -X POST "$API_URL/events/$EVENT_ID/ack" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### ✅ 2. Frontend Dashboard Tests

Open in browser: https://dev.dmmfqlsr845yz.amplifyapp.com

**Dashboard Page** (`/`)
- [ ] Page loads without errors
- [ ] Summary cards display (Total Events, Pending, Delivered, Failed)
- [ ] Event type distribution chart renders
- [ ] Status distribution chart renders
- [ ] Auto-refresh toggle works
- [ ] Manual refresh button works
- [ ] Data updates every 30 seconds when auto-refresh enabled

**Events Page** (`/events`)
- [ ] Page loads without errors
- [ ] Events list table displays
- [ ] Status filter dropdown works (All, Pending, Delivered, Failed)
- [ ] Events show correct data (ID, Type, Status, Created, Delivery Time)
- [ ] Pagination works if > 10 events
- [ ] Status badges have correct colors (pending=blue, delivered=green, failed=red)

**Webhooks Page** (`/webhooks`)
- [ ] Page loads without errors
- [ ] Shows webhook URL configuration
- [ ] Displays API credentials (masked)
- [ ] Shows dispatcher schedule information
- [ ] Recent webhook deliveries list displays

**Navigation**
- [ ] Logo/title links to dashboard
- [ ] All navigation links work
- [ ] Active page is highlighted in nav

### ✅ 3. Error Handling Tests

#### Invalid Authentication
```bash
curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=api" \
  --data-urlencode "password=wrong-key" \
  | jq
# Expected: 401 Unauthorized
```

#### Expired/Invalid Token
```bash
curl -s "$API_URL/inbox" \
  -H "Authorization: Bearer invalid-token" | jq
# Expected: 401 Unauthorized
```

#### Missing Required Fields
```bash
curl -s -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"payload": {}}' | jq
# Expected: 422 Validation Error
```

### ✅ 4. Load Testing (Optional)

#### Create Multiple Events
```bash
for i in {1..10}; do
  curl -s -X POST "$API_URL/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"type\": \"test.event\",
      \"source\": \"load-test\",
      \"payload\": {
        \"iteration\": $i,
        \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"
      }
    }" > /dev/null
  echo "Event $i created"
done

echo "✅ Created 10 test events"
```

#### Verify in Dashboard
1. Open frontend: https://dev.dmmfqlsr845yz.amplifyapp.com
2. Check Total Events count increased by 10
3. Navigate to Events page
4. Verify all 10 events are listed

### ✅ 5. Integration Tests

#### Full Event Lifecycle
```bash
# 1. Create event
EVENT_ID=$(curl -s -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "integration.test",
    "source": "test-suite",
    "payload": {"test": true}
  }' | jq -r '.id')

echo "Created event: $EVENT_ID"

# 2. Verify in inbox
curl -s "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN" \
  | jq ".[] | select(.id == \"$EVENT_ID\")"

# 3. Get event details
curl -s "$API_URL/events/$EVENT_ID" \
  -H "Authorization: Bearer $TOKEN" | jq

# 4. Acknowledge event
curl -s -X POST "$API_URL/events/$EVENT_ID/ack" \
  -H "Authorization: Bearer $TOKEN" | jq

# 5. Verify status changed
curl -s "$API_URL/events/$EVENT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.status'
# Expected: "delivered"
```

## Common Issues & Fixes

### Issue: 401 Unauthorized
**Fix**: Token expired (24 hour expiry). Get a new token:
```bash
export TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=api" \
  --data-urlencode "password=$API_KEY" \
  | jq -r '.access_token')
```

### Issue: Frontend shows "Network Error"
**Fix**: Check that API URL is configured correctly in frontend environment

### Issue: Events not appearing in dashboard
**Fix**:
1. Verify JWT token is valid
2. Check CloudWatch logs for Lambda errors
3. Verify DynamoDB table has data

## Monitoring During Tests

### CloudWatch Logs
```bash
# Tail API Lambda logs
aws logs tail /aws/lambda/amplify-dmmfqlsr845yz-dev-TriggersApiFunction* \
  --region us-east-2 \
  --follow

# Tail Dispatcher Lambda logs
aws logs tail /aws/lambda/amplify-dmmfqlsr845yz-dev-DispatcherFunction* \
  --region us-east-2 \
  --follow
```

### CloudWatch Dashboard
Check metrics at:
https://console.aws.amazon.com/cloudwatch/home?region=us-east-2#dashboards:name=ZapierTriggersAPI-amplify-dmmfqlsr845yz-dev-branch-*

Monitor:
- Lambda invocations
- Error rates
- Duration/latency
- DynamoDB read/write capacity

## Test Data Cleanup

### Delete All Test Events
```bash
# List all events
EVENT_IDS=$(curl -s "$API_URL/events?limit=100" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.[].id')

# Delete each event (Note: DELETE endpoint needs to be implemented)
# For now, events will auto-delete after 90 days (TTL)
```

### Verify Cleanup
```bash
curl -s "$API_URL/events/summary" \
  -H "Authorization: Bearer $TOKEN" | jq
```

## Production Testing

**⚠️ WARNING**: Only test production with real, non-test data

Production URLs:
- Frontend: https://main.dmmfqlsr845yz.amplifyapp.com
- Backend API: https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws

Use production API key from:
```bash
aws secretsmanager list-secrets --region us-east-2 \
  --query 'SecretList[?contains(Name, `zapier-api-credentials-amplify-dmmfqlsr845yz-main-branch`)].Name' \
  --output text
```

## Next Steps

After completing manual testing:
1. Document any bugs found
2. Create GitHub issues for bugs
3. Test dispatcher scheduled execution (wait 5 minutes)
4. Test with real Zapier webhook URL
5. Perform load testing (100+ events)
6. Test error scenarios (network failures, timeouts)
