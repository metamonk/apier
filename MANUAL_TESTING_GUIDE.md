# Manual Testing Guide
## Zapier Triggers API - Complete System Testing

**Last Updated:** 2025-11-14
**Purpose:** Comprehensive manual testing of all system features
**Environment:** Sandbox (recommended) or Local

---

## Table of Contents

1. [Testing Options](#testing-options)
2. [Quick Start](#quick-start)
3. [Feature Testing Checklist](#feature-testing-checklist)
4. [Detailed Testing Steps](#detailed-testing-steps)
5. [Dashboard Testing](#dashboard-testing)
6. [API Testing](#api-testing)
7. [Load Testing](#load-testing)
8. [Troubleshooting](#troubleshooting)

---

## Testing Options

### Option 1: Sandbox Environment (Recommended)

**Pros:**
- Fully deployed AWS infrastructure
- Isolated from production
- No local setup required
- Real-world testing conditions

**Sandbox URLs:**
- Dashboard: `https://sandbox.dmmfqlsr845yz.amplifyapp.com`
- API: `https://vwjsgmo7i5ooweeep6vshc7djy0btmai.lambda-url.us-east-2.on.aws`
- API Key: `sandbox-test-key-12345`

**Setup:**
```bash
export API_URL="https://vwjsgmo7i5ooweeep6vshc7djy0btmai.lambda-url.us-east-2.on.aws"
export API_KEY="sandbox-test-key-12345"
```

---

### Option 2: Production Environment

**Pros:**
- Test actual production system
- Real data

**Cons:**
- Affects production metrics
- Uses real API keys

**Production URLs:**
- Dashboard: [Check AWS Amplify Console]
- API: `https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws`
- API Key: [Get from AWS Secrets Manager]

**Setup:**
```bash
export API_URL="https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws"
# Get API key from Secrets Manager
export API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --region us-east-2 \
  --query SecretString --output text | jq -r '.zapier_api_key')
```

---

### Option 3: Local Development (Amplify Sandbox)

**Pros:**
- Fast iteration
- No AWS costs during testing
- Full control

**Cons:**
- Requires local AWS credentials
- More complex setup

**Setup:**
```bash
# Install dependencies
pnpm install

# Start Amplify sandbox
npx ampx sandbox

# In another terminal, start frontend
cd frontend
npm run dev
```

---

## Quick Start

### Prerequisites

1. **Command-line tools:**
   ```bash
   # Check if you have required tools
   which curl    # HTTP client
   which jq      # JSON processor

   # Install jq if missing (macOS)
   brew install jq
   ```

2. **Environment variables:**
   ```bash
   # Using sandbox (recommended for testing)
   export API_URL="https://vwjsgmo7i5ooweeep6vshc7djy0btmai.lambda-url.us-east-2.on.aws"
   export API_KEY="sandbox-test-key-12345"
   ```

3. **Verify connectivity:**
   ```bash
   curl $API_URL/health
   # Expected: {"status":"healthy"}
   ```

---

## Feature Testing Checklist

### Core Features

- [ ] **API Authentication**
  - [ ] Get JWT token with valid credentials
  - [ ] Reject invalid credentials
  - [ ] Token expires after 24 hours
  - [ ] Can refresh token

- [ ] **Event Ingestion**
  - [ ] Submit single event
  - [ ] Submit event with nested payload
  - [ ] Submit event with array data
  - [ ] Reject malformed JSON
  - [ ] Reject missing required fields
  - [ ] Return proper HTTP status codes

- [ ] **Event Polling**
  - [ ] Get pending events via /inbox
  - [ ] Filter by status
  - [ ] Pagination works
  - [ ] Events ordered by creation time

- [ ] **Event Acknowledgment**
  - [ ] Acknowledge event successfully
  - [ ] Event status changes to delivered
  - [ ] Cannot acknowledge twice
  - [ ] Cannot acknowledge non-existent event

### Dashboard Features

- [ ] **Dashboard Access**
  - [ ] Dashboard loads successfully
  - [ ] Auto-authentication works
  - [ ] All three pages accessible (Dashboard, Events, Webhooks)

- [ ] **Metrics Display**
  - [ ] Event summary cards show correct counts
  - [ ] Success rate calculated correctly
  - [ ] Event lifecycle diagram displays
  - [ ] Latency metrics (P50, P95, P99) display
  - [ ] Throughput metrics display
  - [ ] Error analytics display

- [ ] **Dashboard Functionality**
  - [ ] Auto-refresh works (every 10 seconds)
  - [ ] Manual refresh works
  - [ ] Pause/Resume auto-refresh works
  - [ ] Send Event interface works
  - [ ] Navigation between pages works

- [ ] **Events Management Page**
  - [ ] Event list displays
  - [ ] Filter by status works
  - [ ] Filter by event type works
  - [ ] Search functionality works
  - [ ] Export to CSV works
  - [ ] Export to JSON works
  - [ ] Event details modal works

- [ ] **Webhook Receiver Page**
  - [ ] Webhook stats display
  - [ ] Recent webhooks list displays
  - [ ] Webhook monitoring works

### Advanced Features

- [ ] **Error Handling**
  - [ ] API returns clear error messages
  - [ ] Dashboard shows error states gracefully
  - [ ] Failed events tracked correctly

- [ ] **Performance**
  - [ ] API responds quickly (< 1s)
  - [ ] Dashboard loads quickly (< 3s)
  - [ ] Can handle multiple concurrent requests

- [ ] **Reliability**
  - [ ] Events persist in DynamoDB
  - [ ] Dispatcher processes events
  - [ ] Retry mechanism works
  - [ ] TTL auto-deletes old events (90 days)

---

## Detailed Testing Steps

### Test 1: API Authentication

**Objective:** Verify JWT authentication works correctly

**Steps:**

1. **Get JWT token (valid credentials):**
   ```bash
   curl -X POST "$API_URL/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=api&password=$API_KEY"
   ```

   **Expected:** HTTP 200, JSON with `access_token` and `token_type`

   **Verify:**
   - Token is a long string (JWT format)
   - Token type is "bearer"

2. **Store token:**
   ```bash
   export TOKEN=$(curl -s -X POST "$API_URL/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=api&password=$API_KEY" | jq -r '.access_token')

   echo "Token acquired: ${TOKEN:0:50}..."
   ```

3. **Test invalid credentials:**
   ```bash
   curl -X POST "$API_URL/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=api&password=wrong-password"
   ```

   **Expected:** HTTP 401, error message "Incorrect username or password"

4. **Test protected endpoint without token:**
   ```bash
   curl -X GET "$API_URL/inbox"
   ```

   **Expected:** HTTP 401, "Not authenticated"

**Pass Criteria:**
- ✅ Valid credentials return token
- ✅ Invalid credentials return 401
- ✅ Protected endpoints require token

---

### Test 2: Event Ingestion

**Objective:** Verify event submission works with various payloads

**Steps:**

1. **Submit simple event:**
   ```bash
   curl -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "test.simple",
       "payload": {
         "message": "Hello World",
         "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
       }
     }'
   ```

   **Expected:** HTTP 200, event object with ID, status "pending"

   **Save event ID:**
   ```bash
   EVENT_ID=$(curl -s -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"event_type":"test","payload":{"msg":"test"}}' | jq -r '.id')

   echo "Event ID: $EVENT_ID"
   ```

2. **Submit event with nested payload:**
   ```bash
   curl -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "order.created",
       "payload": {
         "order": {
           "id": "ORD-12345",
           "customer": {
             "name": "Jane Doe",
             "email": "jane@example.com"
           },
           "items": [
             {"product": "Widget", "qty": 2, "price": 29.99},
             {"product": "Gadget", "qty": 1, "price": 49.99}
           ],
           "total": 109.97
         }
       }
     }'
   ```

   **Expected:** HTTP 200, event created successfully

3. **Submit malformed JSON:**
   ```bash
   curl -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"event_type":"test","payload":{'
   ```

   **Expected:** HTTP 422, validation error

4. **Submit without required field:**
   ```bash
   curl -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "test"
     }'
   ```

   **Expected:** HTTP 422, "field required: payload"

**Pass Criteria:**
- ✅ Simple events accepted
- ✅ Nested/complex payloads accepted
- ✅ Malformed JSON rejected with 422
- ✅ Missing required fields rejected

---

### Test 3: Event Polling

**Objective:** Verify event retrieval via /inbox endpoint

**Steps:**

1. **Poll pending events:**
   ```bash
   curl -X GET "$API_URL/inbox" \
     -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** HTTP 200, array of pending events

   **Verify:**
   - Events have `id`, `event_type`, `payload`, `status`, `created_at`
   - Status is "pending"
   - Ordered by creation time (oldest first)

2. **Poll with limit:**
   ```bash
   curl -X GET "$API_URL/inbox?limit=5" \
     -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** Maximum 5 events returned

3. **Verify event appears in inbox:**
   ```bash
   curl -X GET "$API_URL/inbox" \
     -H "Authorization: Bearer $TOKEN" | jq ".[] | select(.id == \"$EVENT_ID\")"
   ```

   **Expected:** Your event from Test 2 appears in results

**Pass Criteria:**
- ✅ Inbox returns pending events
- ✅ Pagination works
- ✅ Events include all required fields

---

### Test 4: Event Acknowledgment

**Objective:** Verify event acknowledgment changes status

**Steps:**

1. **Acknowledge event:**
   ```bash
   curl -X POST "$API_URL/events/$EVENT_ID/acknowledge" \
     -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** HTTP 200, success message

2. **Verify event no longer pending:**
   ```bash
   curl -X GET "$API_URL/inbox" \
     -H "Authorization: Bearer $TOKEN" | jq ".[] | select(.id == \"$EVENT_ID\")"
   ```

   **Expected:** Event not in inbox (empty result)

3. **Try to acknowledge again:**
   ```bash
   curl -X POST "$API_URL/events/$EVENT_ID/acknowledge" \
     -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** HTTP 400 or 404, error message

4. **Try to acknowledge non-existent event:**
   ```bash
   curl -X POST "$API_URL/events/evt_nonexistent/acknowledge" \
     -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** HTTP 404, "Event not found"

**Pass Criteria:**
- ✅ Acknowledgment succeeds
- ✅ Event removed from inbox
- ✅ Cannot acknowledge twice
- ✅ Non-existent events return 404

---

### Test 5: Using Example Scripts

**Objective:** Verify provided example scripts work

**Steps:**

1. **Make scripts executable:**
   ```bash
   chmod +x examples/curl/*.sh
   ```

2. **Run basic flow:**
   ```bash
   ./examples/curl/basic-flow.sh
   ```

   **Expected:** Complete workflow executes successfully
   - Authenticates
   - Creates event
   - Retrieves inbox
   - Acknowledges event

   **Watch output for any errors**

3. **Run bulk events (optional):**
   ```bash
   ./examples/curl/bulk-events.sh 5
   ```

   **Expected:** Creates 5 events successfully

4. **Run polling consumer (optional):**
   ```bash
   # Run in separate terminal, let it run for 1-2 minutes
   ./examples/curl/polling-consumer.sh

   # Stop with Ctrl+C
   ```

   **Expected:** Polls inbox every 10 seconds, processes events

**Pass Criteria:**
- ✅ All scripts execute without errors
- ✅ Scripts produce expected output

---

## Dashboard Testing

### Test 6: Dashboard Access & Navigation

**Objective:** Verify dashboard loads and navigation works

**Steps:**

1. **Open dashboard:**
   ```bash
   # For sandbox
   open https://sandbox.dmmfqlsr845yz.amplifyapp.com

   # Or paste URL in browser
   ```

2. **Verify dashboard loads:**
   - ✅ Page loads within 3 seconds
   - ✅ No JavaScript errors in console (F12 → Console)
   - ✅ Event summary cards display
   - ✅ Charts render

3. **Test navigation:**
   - Click "Events Management" → Events page loads
   - Click "Webhook Receiver" → Webhooks page loads
   - Click logo or "Dashboard" → Returns to main dashboard

4. **Verify responsive design:**
   - Resize browser window
   - ✅ Layout adapts to smaller screens
   - Test on mobile device (optional)

**Pass Criteria:**
- ✅ Dashboard loads successfully
- ✅ All pages accessible
- ✅ Navigation works
- ✅ No console errors

---

### Test 7: Event Summary Metrics

**Objective:** Verify metrics display correctly

**Steps:**

1. **Check event summary cards:**
   - **Total Events:** Shows cumulative count
   - **Pending:** Shows events awaiting delivery
   - **Delivered:** Shows successfully delivered events
   - **Failed:** Shows failed events
   - **Success Rate:** Shows percentage (Delivered / (Delivered + Failed))

2. **Verify calculations:**
   - Manual check: Success Rate = (Delivered / (Delivered + Failed)) × 100
   - Example: Delivered=100, Failed=5 → Success Rate = 95.24%

3. **Submit test event and watch metrics update:**
   ```bash
   # Submit event
   curl -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"event_type":"test.dashboard","payload":{"test":true}}'

   # Watch dashboard - Total Events should increase by 1
   ```

4. **Test auto-refresh:**
   - Note "Last Updated" timestamp
   - Wait 10 seconds
   - ✅ Timestamp updates automatically

5. **Test manual refresh:**
   - Click refresh button (circular arrow icon)
   - ✅ Timestamp updates immediately

**Pass Criteria:**
- ✅ All metrics display
- ✅ Calculations are correct
- ✅ Metrics update after new events
- ✅ Auto-refresh works

---

### Test 8: Event Lifecycle Diagram

**Objective:** Verify flow diagram displays correctly

**Steps:**

1. **Verify diagram elements:**
   - ✅ "Created" box with count
   - ✅ "Pending" box with count
   - ✅ "Delivered" box with count
   - ✅ "Failed" box with count
   - ✅ Arrows connecting states

2. **Verify flow logic:**
   - All events start at "Created"
   - Flow to "Pending"
   - Branch to either "Delivered" or "Failed"

3. **Check counts match:**
   - Created count = Total Events
   - Pending count = Pending Events card
   - Delivered count = Delivered Events card
   - Failed count = Failed Events card

**Pass Criteria:**
- ✅ Diagram displays correctly
- ✅ Counts match summary cards
- ✅ Flow logic is clear

---

### Test 9: Performance Metrics Charts

**Objective:** Verify latency and throughput charts

**Steps:**

1. **Latency Chart:**
   - ✅ Shows P50, P95, P99 percentiles
   - ✅ Values are in seconds
   - ✅ Bar chart displays
   - ✅ Sample size shown

2. **Throughput Chart:**
   - ✅ Shows events per minute
   - ✅ Shows events per hour
   - ✅ Shows events per day
   - ✅ Time range indicated (last 24 hours)

3. **Verify values are reasonable:**
   - P50 should be < P95 < P99
   - Throughput should match recent activity

**Pass Criteria:**
- ✅ Both charts display
- ✅ Values are reasonable
- ✅ No "NaN" or error values

---

### Test 10: Events Management Page

**Objective:** Verify event list and filtering

**Steps:**

1. **Navigate to Events page:**
   - Click "Events Management"

2. **Verify event list:**
   - ✅ Events displayed in table/list
   - ✅ Shows event ID, type, status, timestamp
   - ✅ List is scrollable

3. **Test filtering:**
   - Filter by status = "pending"
     - ✅ Only pending events shown
   - Filter by status = "delivered"
     - ✅ Only delivered events shown
   - Filter by status = "failed"
     - ✅ Only failed events shown
   - Clear filter
     - ✅ All events shown

4. **Test search:**
   - Search by event type (e.g., "test")
     - ✅ Matching events shown
   - Search by event ID
     - ✅ Specific event shown
   - Clear search
     - ✅ All events shown

5. **Test export:**
   - Click "Export" → Select "CSV"
     - ✅ CSV file downloads
     - ✅ Contains event data
   - Click "Export" → Select "JSON"
     - ✅ JSON file downloads
     - ✅ Valid JSON format

6. **Test event details:**
   - Click on an event
     - ✅ Modal or detail view opens
     - ✅ Shows full event payload
     - ✅ Shows metadata (ID, status, timestamps)

**Pass Criteria:**
- ✅ Event list displays
- ✅ All filters work
- ✅ Search works
- ✅ Export works
- ✅ Event details accessible

---

### Test 11: Send Event Interface

**Objective:** Verify dashboard event submission

**Steps:**

1. **Open Send Event dialog:**
   - Click "Send Event" button (top-right)
   - ✅ Modal/dialog opens

2. **Submit event:**
   - Event Type: `test.dashboard.submit`
   - Source: `dashboard-ui`
   - Payload: `{"test": true, "timestamp": "2025-11-14T12:00:00Z"}`
   - Click "Send Event"

3. **Verify submission:**
   - ✅ Success message appears
   - ✅ Dialog closes
   - ✅ Total Events count increases
   - ✅ Event appears in Events Management page

4. **Test validation:**
   - Try to submit without event type
     - ✅ Error message shown
   - Try to submit invalid JSON in payload
     - ✅ Error message shown

**Pass Criteria:**
- ✅ Can submit events via UI
- ✅ Events appear in system
- ✅ Validation works

---

## API Testing

### Test 12: API Documentation

**Objective:** Verify Swagger/OpenAPI docs are accessible

**Steps:**

1. **Access Swagger UI:**
   ```bash
   open $API_URL/docs
   ```

2. **Verify documentation:**
   - ✅ Swagger UI loads
   - ✅ All endpoints listed
   - ✅ Request/response schemas shown
   - ✅ Can test endpoints interactively

3. **Test an endpoint:**
   - Click `/health` endpoint
   - Click "Try it out"
   - Click "Execute"
   - ✅ Response shown inline

**Pass Criteria:**
- ✅ Documentation accessible
- ✅ All endpoints documented
- ✅ Interactive testing works

---

### Test 13: Error Handling

**Objective:** Verify API returns proper error responses

**Test Cases:**

1. **404 Not Found:**
   ```bash
   curl -X GET "$API_URL/nonexistent" \
     -H "Authorization: Bearer $TOKEN"
   ```
   **Expected:** HTTP 404, error message

2. **405 Method Not Allowed:**
   ```bash
   curl -X DELETE "$API_URL/health"
   ```
   **Expected:** HTTP 405

3. **422 Validation Error:**
   ```bash
   curl -X POST "$API_URL/events" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"wrong_field": "value"}'
   ```
   **Expected:** HTTP 422, validation details

4. **401 Unauthorized:**
   ```bash
   curl -X GET "$API_URL/inbox"
   ```
   **Expected:** HTTP 401, "Not authenticated"

**Pass Criteria:**
- ✅ All error codes correct
- ✅ Error messages are clear
- ✅ JSON error format consistent

---

## Load Testing

### Test 14: Load Testing (Optional)

**Objective:** Test system under load

**Prerequisites:**
```bash
# Install k6 (load testing tool)
brew install k6  # macOS
```

**Steps:**

1. **Run baseline test:**
   ```bash
   npm run load-test:baseline
   ```

   **Expected:** Test completes, generates report

   **Review metrics:**
   - Request rate (RPS)
   - Response time percentiles
   - Error rate

2. **Run moderate load test:**
   ```bash
   npm run load-test:moderate
   ```

   **Expected:** System handles moderate load

3. **Review results:**
   ```bash
   ls results/
   cat results/baseline-*.json
   ```

**Pass Criteria:**
- ✅ Tests complete without errors
- ✅ P95 response time < 5s
- ✅ Error rate < 1%

---

## Troubleshooting

### Dashboard Not Loading

**Symptoms:**
- White screen
- "Error loading data"
- Infinite loading spinner

**Solutions:**

1. **Check browser console:**
   - F12 → Console tab
   - Look for error messages

2. **Verify API connectivity:**
   ```bash
   curl $API_URL/health
   ```

3. **Check API key configuration:**
   - Dashboard auto-authenticates with configured API key
   - Verify `.env` file in frontend directory

4. **Clear browser cache:**
   - Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

---

### API Authentication Failing

**Symptoms:**
- 401 Unauthorized errors
- "Incorrect username or password"

**Solutions:**

1. **Verify API key:**
   ```bash
   echo $API_KEY
   # Should not be empty
   ```

2. **Check for whitespace:**
   ```bash
   export API_KEY=$(echo $API_KEY | tr -d '[:space:]')
   ```

3. **Get fresh API key:**
   ```bash
   # For sandbox
   export API_KEY="sandbox-test-key-12345"

   # For production
   aws secretsmanager get-secret-value \
     --secret-id zapier-api-credentials-{stackName} \
     --region us-east-2
   ```

---

### Events Not Appearing

**Symptoms:**
- Events submitted but not in inbox
- Dashboard shows 0 events

**Solutions:**

1. **Check event was created:**
   ```bash
   # Should return event with ID
   curl -X POST "$API_URL/events" ...
   ```

2. **Check event status:**
   - May have been delivered/acknowledged already
   - Check Events Management page (all statuses)

3. **Verify dashboard refresh:**
   - Wait 10 seconds for auto-refresh
   - Or click manual refresh button

---

## Testing Checklist Summary

### Quick Test (10 minutes)

- [ ] Health check passes
- [ ] Can authenticate and get token
- [ ] Can submit event
- [ ] Event appears in inbox
- [ ] Dashboard loads and shows metrics
- [ ] Can acknowledge event

### Full Test (30-60 minutes)

- [ ] Complete all API tests (Tests 1-5)
- [ ] Complete all Dashboard tests (Tests 6-11)
- [ ] Test API documentation (Test 12)
- [ ] Test error handling (Test 13)
- [ ] Review example scripts

### Comprehensive Test (2+ hours)

- [ ] Everything in Full Test
- [ ] Load testing (Test 14)
- [ ] Test all edge cases
- [ ] Test with multiple users
- [ ] Test all export formats
- [ ] Test all filtering combinations
- [ ] Review CloudWatch logs (if access available)

---

## Next Steps After Testing

### If Tests Pass ✅

1. Document any observations
2. Note performance metrics
3. Consider additional features/improvements
4. Ready for production use!

### If Tests Fail ❌

1. Document specific failure
2. Check troubleshooting section
3. Review CloudWatch logs
4. Open issue with:
   - Test that failed
   - Expected vs actual behavior
   - Error messages
   - Steps to reproduce

---

## Additional Resources

- **[Quickstart Guide](./docs/QUICKSTART.md)** - 5-minute setup
- **[Developer Guide](./docs/DEVELOPER_GUIDE.md)** - Integration guide
- **[Dashboard User Guide](./docs/DASHBOARD_USER_GUIDE.md)** - Dashboard features
- **[Examples README](./examples/README.md)** - Code examples
- **[UAT Test Plan](./.taskmaster/docs/uat-test-plan.md)** - Detailed test scenarios

---

**Happy Testing!** 🚀
