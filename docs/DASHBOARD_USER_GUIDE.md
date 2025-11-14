# API/er Dashboard - User Guide

A comprehensive guide for using the API/er monitoring dashboard to track event delivery, monitor system health, and interpret performance metrics.

## Table of Contents

- [Dashboard Overview](#dashboard-overview)
- [Getting Started](#getting-started)
- [Dashboard Components](#dashboard-components)
- [Interpreting Metrics](#interpreting-metrics)
- [Common Use Cases](#common-use-cases)
- [Best Practices](#best-practices)
- [FAQ](#faq)

## Dashboard Overview

The API/er dashboard provides real-time visibility into your event delivery pipeline. It helps you:

- **Monitor Health**: Track success rates and identify delivery issues
- **Analyze Performance**: Understand latency and throughput patterns
- **Troubleshoot Issues**: Identify and diagnose delivery failures
- **Optimize Operations**: Make data-driven decisions about scaling and configuration

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│ Header: API/er Logo | Refresh Controls | Send Event     │
├─────────────────────────────────────────────────────────┤
│ Quick Navigation: [Events Management] [Webhooks]        │
├─────────────────────────────────────────────────────────┤
│ Event Summary: Cards showing Total/Pending/Delivered... │
├─────────────────────────────────────────────────────────┤
│ Event Lifecycle: Visual flow diagram                    │
├─────────────────────────────────────────────────────────┤
│ Performance Metrics: Latency & Throughput Charts        │
└─────────────────────────────────────────────────────────┘
```

## Getting Started

### Accessing the Dashboard

1. **Open Dashboard URL**: Navigate to your deployed Amplify URL (e.g., `https://main.d1234.amplifyapp.com`)
2. **Automatic Authentication**: The dashboard automatically authenticates using the configured API key
3. **Wait for Data Load**: Initial load takes 2-3 seconds to fetch metrics from the backend

### Dashboard Controls

**Top-Right Controls**:
- **Last Updated Time**: Shows when metrics were last refreshed (e.g., "Updated 10:45:32 AM")
- **Send Event**: Button to quickly submit a test event
- **Refresh**: Manual refresh button (circular arrow icon)
- **Pause/Resume**: Toggle auto-refresh (updates every 10 seconds by default)

**Quick Navigation**:
- **Events Management**: View all events with filtering and export capabilities
- **Webhook Receiver**: Monitor incoming webhook events

## Dashboard Components

### 1. Event Summary Cards

Four large cards displaying key metrics:

#### Total Events Card
```
┌─────────────────────┐
│ Total Events        │
│                     │
│      1,247          │
│                     │
│ All events created  │
└─────────────────────┘
```

**What It Shows**: Cumulative count of all events in the system (across all statuses)

**What It Means**:
- Increasing steadily = Healthy event ingestion
- Flat line = No new events (possible integration issue)
- Sudden spike = Check for unusual activity or load

**Action Items**:
- Monitor growth rate over time
- Compare with expected event volume
- Investigate if flat or dropping unexpectedly

---

#### Pending Events Card
```
┌─────────────────────┐
│ Pending             │
│                     │
│       23            │
│                     │
│ Awaiting delivery   │
└─────────────────────┘
```

**What It Shows**: Events currently queued for delivery to webhooks

**What It Means**:
- Low pending (< 50) = Dispatcher keeping up with load
- Medium pending (50-200) = Normal during peak times
- High pending (> 500) = Delivery backlog, investigate dispatcher

**Action Items**:
- If consistently high, check dispatcher CloudWatch logs
- Verify webhook endpoints are responding quickly
- Consider increasing dispatcher frequency (currently every 5 minutes)

---

#### Delivered Events Card
```
┌─────────────────────┐
│ Delivered           │
│                     │
│     1,198           │
│                     │
│ Successfully sent   │
└─────────────────────┘
```

**What It Shows**: Events successfully delivered to webhook endpoints

**What It Means**:
- Increasing = Healthy delivery pipeline
- Percentage of total should be > 95%

**Action Items**:
- Compare with Total to calculate rough success rate
- If delivery rate is low, check Failed events

---

#### Failed Events Card
```
┌─────────────────────┐
│ Failed              │
│                     │
│       26            │
│                     │
│ Exceeded retries    │
└─────────────────────┘
```

**What It Shows**: Events that failed delivery after maximum retry attempts

**What It Means**:
- Low count (< 5%) = Normal error rate
- Rising count = Webhook endpoint issues
- Specific error patterns = Check error metrics for details

**Action Items**:
- Click through to Events page and filter by status="failed"
- Review error_message field for common patterns
- Verify webhook URL is correct and responding
- Check webhook endpoint logs for 4xx/5xx errors

---

#### Success Rate Badge
```
┌─────────────────────┐
│ Success Rate        │
│                     │
│     97.91%          │
│                     │
│ Delivered/Total     │
└─────────────────────┘
```

**What It Shows**: (Delivered / (Delivered + Failed)) × 100

**What It Means**:
- > 95% = Excellent health
- 90-95% = Good, monitor for trends
- < 90% = Action required

**Action Items**:
- If dropping below 95%, investigate failed events
- Set up CloudWatch alarms for success rate thresholds

### 2. Event Lifecycle Flow

Visual diagram showing the event journey:

```
┌──────────┐      ┌──────────┐      ┌────────────┐
│ Created  │─────>│ Pending  │─────>│ Delivered  │
│  1,247   │      │    23    │      │   1,198    │
└──────────┘      └──────────┘      └────────────┘
                       │
                       └────────────>┌──────────┐
                                    │ Failed   │
                                    │    26    │
                                    └──────────┘
```

**How to Read It**:
1. **Created**: All events start here when submitted via `POST /events`
2. **Pending**: Events awaiting delivery (picked up by dispatcher every 5 minutes)
3. **Delivered**: Successfully sent to webhook endpoint (HTTP 200 response)
4. **Failed**: Exceeded maximum retry attempts (typically 3 retries)

**Visual Indicators**:
- **Arrow thickness**: Indicates flow volume (thicker = more events)
- **Color coding**: Green (delivered), Orange (pending), Red (failed)
- **Numbers**: Current count in each state

**What to Watch For**:
- Large pending count that doesn't decrease = Dispatcher issue
- High flow to failed = Webhook endpoint problems
- Balanced flow = Healthy pipeline

### 3. Performance Metrics Charts

Two side-by-side charts showing latency and throughput:

#### Latency Chart (Left)
```
┌─────────────────────────────┐
│ Delivery Latency            │
│                             │
│ P99 ▓▓▓▓▓▓▓▓▓▓▓▓░  5.67s    │
│ P95 ▓▓▓▓▓▓▓░░░░░░  3.45s    │
│ P50 ▓▓░░░░░░░░░░░  1.23s    │
│                             │
│ Sample: 1,150 events        │
└─────────────────────────────┘
```

**What It Shows**: Time from event creation to successful delivery

**Percentile Explanation**:
- **P50 (Median)**: 50% of events deliver faster than this
- **P95**: 95% of events deliver faster than this (only 5% slower)
- **P99**: 99% of events deliver faster than this (only 1% slower)

**Example Interpretation**:
```
P50: 1.23s  → Half of events deliver in under 1.23 seconds
P95: 3.45s  → 95% of events deliver in under 3.45 seconds
P99: 5.67s  → 99% of events deliver in under 5.67 seconds
```

**What Good Latency Looks Like**:
- P50 < 2s: Excellent
- P95 < 5s: Good
- P99 < 10s: Acceptable

**Red Flags**:
- P50 > 5s: Webhook endpoint slow or network issues
- P95 > 15s: Serious performance degradation
- Large gap between P95 and P99: Investigate outliers

**Action Items**:
1. **High P50**: Check webhook endpoint performance and network latency
2. **High P95/P99**: Look for timeout issues or slow webhook responses
3. **Increasing trend**: Monitor webhook server CPU/memory usage

---

#### Throughput Chart (Right)
```
┌─────────────────────────────┐
│ Event Throughput            │
│                             │
│ Per Minute:  12.5 events    │
│ Per Hour:    750 events     │
│ Per Day:     18,000 events  │
│                             │
│ Last 24 hours               │
└─────────────────────────────┘
```

**What It Shows**: Rate of event creation over time

**Metrics Explained**:
- **Events per minute**: Average across last 24 hours
- **Events per hour**: Total events / 24
- **Events per day**: Total count in rolling 24-hour window

**Example Scenarios**:

**Normal Load**:
```
Per Minute: 10-15 events
Per Hour: 600-900 events
Per Day: 14,400-21,600 events
```

**Peak Load** (e.g., marketing campaign):
```
Per Minute: 50+ events
Per Hour: 3,000+ events
Per Day: 72,000+ events
```

**Low Activity**:
```
Per Minute: < 1 event
Per Hour: < 60 events
Per Day: < 1,440 events
```

**Action Items**:
- **Unexpected drop**: Check event source integration
- **Sudden spike**: Verify it's expected (campaign, product launch)
- **Sustained high throughput**: Consider scaling dispatcher frequency

### 4. Send Event Sheet

Quick event submission interface:

```
┌─────────────────────────────┐
│ Send Event                  │
│                             │
│ Event Type: [user.created]  │
│ Source:     [dashboard]     │
│ Payload:    {...}           │
│                             │
│ [Send Event] [Cancel]       │
└─────────────────────────────┘
```

**Use Cases**:
- Test end-to-end delivery pipeline
- Verify webhook endpoint connectivity
- Demonstrate system functionality
- Create sample data for testing

**How to Use**:
1. Click "Send Event" button in top-right
2. Fill in event type (e.g., "user.created")
3. Fill in source (e.g., "test-dashboard")
4. Add JSON payload (e.g., `{"user_id": "12345"}`)
5. Click "Send Event"
6. Watch dashboard update with new event

## Interpreting Metrics

### Health Indicators

#### Green (Healthy)
- Success rate > 95%
- P50 latency < 2s
- Pending count < 50
- Steady throughput

**What to Do**: Monitor normally, review metrics weekly

---

#### Yellow (Warning)
- Success rate 90-95%
- P50 latency 2-5s
- Pending count 50-200
- Throughput variance > 50%

**What to Do**: Investigate trends, check webhook logs, consider optimization

---

#### Red (Critical)
- Success rate < 90%
- P50 latency > 5s
- Pending count > 500
- Throughput dropped by > 80%

**What to Do**: Immediate investigation, check CloudWatch alarms, review error logs

### Metric Relationships

**Success Rate vs. Failed Events**:
```
Success Rate = (Delivered / (Delivered + Failed)) × 100

Example:
Delivered: 1,198
Failed: 26
Success Rate = (1,198 / (1,198 + 26)) × 100 = 97.91%
```

**Throughput vs. Pending**:
- If throughput increases but pending stays low = Dispatcher keeping up
- If throughput increases and pending rises = Dispatcher overwhelmed
- If throughput drops but pending rises = Delivery issue

**Latency vs. Success Rate**:
- High latency + low success rate = Webhook timeouts
- Normal latency + low success rate = Webhook returning errors
- High latency + high success rate = Slow but functional webhook

## Common Use Cases

### Use Case 1: Daily Health Check

**Goal**: Verify system is operating normally

**Steps**:
1. Open dashboard
2. Check success rate: Should be > 95%
3. Review pending count: Should be < 50
4. Check latency P50: Should be < 2s
5. Verify throughput matches expected volume

**Time Required**: 2 minutes

---

### Use Case 2: Troubleshooting Failed Deliveries

**Goal**: Identify why events are failing

**Steps**:
1. Check Failed count on dashboard
2. Navigate to Events page (click "Events Management")
3. Filter by status="failed"
4. Review error_message field for patterns
5. Common errors:
   - "Connection timeout" → Webhook endpoint slow
   - "404 Not Found" → Webhook URL incorrect
   - "401 Unauthorized" → Signature validation failing

**Time Required**: 5-10 minutes

---

### Use Case 3: Performance Investigation

**Goal**: Understand why latency is high

**Steps**:
1. Check latency chart on dashboard
2. Note P50, P95, P99 values
3. Navigate to CloudWatch (see MONITORING.md)
4. Review webhook endpoint metrics
5. Check network latency between Lambda and webhook
6. Review dispatcher logs for retry patterns

**Time Required**: 15-30 minutes

---

### Use Case 4: Capacity Planning

**Goal**: Determine if system needs scaling

**Steps**:
1. Review throughput metrics over 7 days
2. Identify peak usage hours
3. Check if pending count spikes during peaks
4. Calculate average events per minute
5. Compare with expected future load
6. Recommendations:
   - If current peak is 80% of capacity → Plan scaling
   - If pending consistently > 100 → Increase dispatcher frequency
   - If latency P95 > 5s → Optimize webhook endpoint

**Time Required**: 30 minutes

---

### Use Case 5: Demo/Testing

**Goal**: Show system functionality to stakeholders

**Steps**:
1. Open dashboard in presentation mode (full screen)
2. Click "Send Event"
3. Create sample event (e.g., `type: "demo.test"`)
4. Watch event appear in Total count
5. Wait for dispatcher cycle (5 minutes max)
6. Watch event move from Pending to Delivered
7. Show latency metrics update

**Time Required**: 5-10 minutes (including dispatcher wait)

## Best Practices

### Monitoring Frequency

**Daily Check** (2 minutes):
- Success rate > 95%
- Pending count < 50
- No critical errors

**Weekly Review** (15 minutes):
- Throughput trends
- Latency percentile trends
- Top error messages
- Capacity planning

**Monthly Analysis** (1 hour):
- Compare metrics month-over-month
- Identify optimization opportunities
- Review scaling requirements
- Update alerting thresholds

### Alerting Strategy

Set up CloudWatch alarms for:

**Critical Alerts** (immediate action):
- Success rate < 90% for 10 minutes
- Pending count > 500 for 15 minutes
- P99 latency > 30s for 10 minutes

**Warning Alerts** (investigate within 1 hour):
- Success rate < 95% for 30 minutes
- Pending count > 200 for 30 minutes
- Failed events > 50 in 1 hour

**Info Alerts** (review daily):
- Throughput variance > 50%
- Latency P95 > 5s for 1 hour

See [docs/MONITORING.md](./MONITORING.md) for alarm configuration.

### Data Retention

**Dashboard Metrics**:
- Summary: Real-time (last scan of DynamoDB)
- Latency: Last 24 hours of delivered events
- Throughput: Rolling 24-hour window
- Errors: All failed events (until auto-deleted)

**DynamoDB TTL**:
- All events auto-delete after 90 days (GDPR/CCPA compliance)
- Export critical events before deletion if needed
- See [Events Management](#dashboard-components) for export functionality

### Performance Optimization

**Dashboard Load Time**:
- Initial load: 2-3 seconds (JWT auth + metrics fetch)
- Refresh: 1-2 seconds (metrics only)
- Auto-refresh: Every 10 seconds (configurable via Pause)

**Reduce Load Time**:
1. Warm Lambda: Configure reserved concurrency
2. Optimize queries: Ensure GSI usage (already configured)
3. Use CDN: Amplify CloudFront distribution caches static assets

**Browser Compatibility**:
- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- Mobile: Responsive design, all features work

## FAQ

### General Questions

**Q: How often does the dashboard refresh?**
A: Every 10 seconds by default. Click "Pause" to stop auto-refresh.

**Q: Can I export metrics data?**
A: Navigate to Events Management page for CSV/JSON export. Dashboard metrics are real-time calculated, not stored.

**Q: Why are my metrics not loading?**
A: Check authentication (API key in `.env`), Lambda CloudWatch logs, and network connectivity. See [Troubleshooting](./DASHBOARD.md#troubleshooting).

**Q: What's the difference between Total and Delivered?**
A: Total includes all events (pending, delivered, failed). Delivered only counts successfully sent events.

### Metrics Questions

**Q: What's a good success rate?**
A: Target > 95%. Anything above 98% is excellent. Below 90% requires immediate investigation.

**Q: Why is P99 so much higher than P50?**
A: P99 captures outliers (slowest 1% of events). Large gaps indicate occasional slow deliveries, often due to webhook endpoint variance.

**Q: What causes high pending count?**
A: Either high event volume exceeding dispatcher capacity, or slow webhook endpoints. Check CloudWatch metrics for dispatcher and webhook latency.

**Q: How is latency calculated?**
A: Time from event creation (`created_at`) to successful delivery (when dispatcher gets HTTP 200). Excludes retry delays.

### Operational Questions

**Q: Can I test event delivery?**
A: Yes! Click "Send Event" button to submit a test event and watch it flow through the pipeline.

**Q: How do I view individual event details?**
A: Navigate to Events Management page, search by event ID or filter by attributes.

**Q: What happens to failed events?**
A: They remain in DynamoDB with status="failed" for 90 days, then auto-delete via TTL.

**Q: Can I manually retry failed events?**
A: Not directly from the dashboard. Use the API endpoint `POST /inbox/{event_id}/retry` (see Developer Guide).

### Technical Questions

**Q: Where is data stored?**
A: DynamoDB table `zapier-triggers-events-{stackName}` with 90-day TTL.

**Q: Is data encrypted?**
A: Yes. TLS in transit, DynamoDB encryption at rest (AWS managed keys).

**Q: Can I customize refresh interval?**
A: Yes, edit `REFRESH_INTERVAL` in `frontend/src/pages/DashboardPage/index.tsx` (default: 10000ms).

**Q: Does the dashboard work offline?**
A: No. Requires network connectivity to fetch metrics from Lambda API.

### Troubleshooting Questions

**Q: Dashboard shows "Authentication Error"**
A: Verify `VITE_API_KEY` in `.env` matches the API key in Secrets Manager. See [DASHBOARD.md Troubleshooting](./DASHBOARD.md#dashboard-shows-authentication-error).

**Q: Metrics loading forever**
A: Check Lambda CloudWatch logs for errors, verify DynamoDB table health, test API endpoints directly with curl.

**Q: Stale data showing**
A: Click "Refresh" button. If issue persists, check browser console for network errors.

**Q: Dashboard slow to load**
A: Lambda cold start adds 2-3 seconds. Consider reserved concurrency or provisioned concurrency for production.

## Additional Resources

- **[Dashboard Technical Documentation](./DASHBOARD.md)**: Architecture, API reference, setup
- **[Monitoring Guide](./MONITORING.md)**: CloudWatch metrics, alarms, logs
- **[Events Management Guide](./EVENTS_MANAGEMENT.md)**: Filtering, export, search (TODO)
- **[Deployment Guide](./DEPLOYMENT.md)**: Multi-environment setup, CI/CD
- **[Developer Guide](./DEVELOPER_GUIDE.md)**: API integration, code examples

---

**Last Updated**: 2025-11-13
**Dashboard Version**: 1.0.0
**For Support**: See [Troubleshooting](./DASHBOARD.md#troubleshooting) or open GitHub issue
