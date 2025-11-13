# Scheduled Events Pattern

Generate events on a schedule for periodic tasks like reports, reminders, and batch jobs.

## Overview

```
Cron/Scheduler → Event Generator → Zapier Triggers API → Zapier Workflows
                   (Script)
```

## Why Use This Pattern?

**Benefits:**
- **Automated Workflows** - Trigger Zapier on a schedule
- **Flexible Scheduling** - Use cron, AWS EventBridge, or any scheduler
- **Reliable Execution** - Events buffered until Zapier acknowledges
- **Historical Records** - All scheduled events tracked in DynamoDB
- **Easy Debugging** - Review event history in CloudWatch

**Use Cases:**
- Daily/weekly reports
- Monthly billing reminders
- Periodic data exports
- Scheduled notifications
- Batch processing triggers

## Implementation

### 1. Simple Cron Job (Bash)

```bash
#!/bin/bash
#
# daily_report.sh - Generate daily report event
# Run via cron: 0 9 * * * /path/to/daily_report.sh
#

API_URL="${API_URL:-https://your-api-url.lambda-url.us-east-2.on.aws}"
API_KEY="${API_KEY:-your-api-key}"

# Get JWT token
TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY" | jq -r '.access_token')

# Generate report data
REPORT_DATE=$(date -d "yesterday" +%Y-%m-%d)
REPORT_DATA=$(cat <<EOF
{
  "date": "$REPORT_DATE",
  "total_sales": 12543.99,
  "total_orders": 87,
  "new_customers": 23,
  "top_products": ["Product A", "Product B", "Product C"]
}
EOF
)

# Send event
RESPONSE=$(curl -s -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"report.daily\",
    \"source\": \"cron-job\",
    \"payload\": $REPORT_DATA
  }")

EVENT_ID=$(echo "$RESPONSE" | jq -r '.id')

echo "$(date): Created daily report event: $EVENT_ID"
```

**Crontab entry:**
```cron
# Run daily at 9:00 AM
0 9 * * * /path/to/daily_report.sh >> /var/log/daily_report.log 2>&1

# Run weekly on Monday at 10:00 AM
0 10 * * 1 /path/to/weekly_summary.sh >> /var/log/weekly_summary.log 2>&1

# Run monthly on 1st at 8:00 AM
0 8 1 * * /path/to/monthly_billing.sh >> /var/log/monthly_billing.log 2>&1
```

### 2. Python Script

```python
#!/usr/bin/env python3
"""
daily_report.py - Generate daily report event

Usage:
    python daily_report.py

Crontab:
    0 9 * * * /usr/bin/python3 /path/to/daily_report.py
"""

import os
import sys
import requests
from datetime import datetime, timedelta
import logging

# Configuration
API_URL = os.environ.get("ZAPIER_API_URL")
API_KEY = os.environ.get("ZAPIER_API_KEY")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_token():
    """Authenticate and get JWT token"""
    response = requests.post(
        f"{API_URL}/token",
        data={"username": "api", "password": API_KEY}
    )
    response.raise_for_status()
    return response.json()["access_token"]

def generate_report():
    """Generate report data for yesterday"""
    yesterday = datetime.now() - timedelta(days=1)

    # Example: Query your database for metrics
    # In real implementation, fetch from database or data warehouse

    return {
        "date": yesterday.strftime("%Y-%m-%d"),
        "period": "daily",
        "metrics": {
            "total_sales": 12543.99,
            "total_orders": 87,
            "new_customers": 23,
            "returning_customers": 64,
            "average_order_value": 144.18
        },
        "top_products": [
            {"id": "prod_1", "name": "Product A", "sales": 3500.00},
            {"id": "prod_2", "name": "Product B", "sales": 2800.00},
            {"id": "prod_3", "name": "Product C", "sales": 1900.00}
        ],
        "generated_at": datetime.now().isoformat()
    }

def send_event(token, report_data):
    """Send event to Zapier API"""
    response = requests.post(
        f"{API_URL}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "type": "report.daily",
            "source": "scheduled-job",
            "payload": report_data
        }
    )
    response.raise_for_status()
    return response.json()

def main():
    try:
        logger.info("Starting daily report generation")

        # Authenticate
        logger.info("Authenticating with API")
        token = get_token()

        # Generate report
        logger.info("Generating report data")
        report_data = generate_report()

        # Send event
        logger.info("Sending event to Zapier API")
        result = send_event(token, report_data)

        logger.info(f"Report event created: {result['id']}")
        logger.info(f"Status: {result['status']}")

        return 0

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

### 3. AWS Lambda + EventBridge

Serverless scheduled events using AWS Lambda and EventBridge.

**Lambda Function:**
```python
# lambda_function.py
import os
import json
import boto3
import requests
from datetime import datetime, timedelta

# Configuration
API_URL = os.environ['ZAPIER_API_URL']
API_KEY = os.environ['ZAPIER_API_KEY']

# Clients
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

def get_token():
    """Get JWT token"""
    response = requests.post(
        f"{API_URL}/token",
        data={"username": "api", "password": API_KEY},
        timeout=5
    )
    response.raise_for_status()
    return response.json()["access_token"]

def generate_daily_report():
    """Generate daily report from DynamoDB"""
    # Example: Query your DynamoDB table for metrics
    table = dynamodb.Table('orders')

    yesterday = datetime.now() - timedelta(days=1)
    start_date = yesterday.replace(hour=0, minute=0, second=0)
    end_date = yesterday.replace(hour=23, minute=59, second=59)

    # Query orders from yesterday
    response = table.scan(
        FilterExpression='created_at BETWEEN :start AND :end',
        ExpressionAttributeValues={
            ':start': start_date.isoformat(),
            ':end': end_date.isoformat()
        }
    )

    orders = response['Items']

    # Calculate metrics
    total_sales = sum(float(order['total']) for order in orders)
    total_orders = len(orders)

    return {
        "date": yesterday.strftime("%Y-%m-%d"),
        "period": "daily",
        "metrics": {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "average_order_value": total_sales / total_orders if total_orders > 0 else 0
        },
        "generated_at": datetime.now().isoformat()
    }

def send_event(token, event_data):
    """Send event to Zapier API"""
    response = requests.post(
        f"{API_URL}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=event_data,
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def publish_metric(metric_name, value):
    """Publish custom metric to CloudWatch"""
    cloudwatch.put_metric_data(
        Namespace='ScheduledJobs',
        MetricData=[
            {
                'MetricName': metric_name,
                'Value': value,
                'Unit': 'Count',
                'Timestamp': datetime.now()
            }
        ]
    )

def lambda_handler(event, context):
    """
    Lambda handler triggered by EventBridge
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # Authenticate
        print("Authenticating with API")
        token = get_token()

        # Generate report
        print("Generating daily report")
        report_data = generate_daily_report()

        # Send event
        print("Sending event to Zapier API")
        result = send_event(token, {
            "type": "report.daily",
            "source": "lambda-scheduled",
            "payload": report_data
        })

        print(f"Event created: {result['id']}")

        # Publish success metric
        publish_metric('DailyReportSuccess', 1)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Report generated successfully',
                'event_id': result['id']
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")

        # Publish failure metric
        publish_metric('DailyReportFailure', 1)

        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Failed to generate report',
                'error': str(e)
            })
        }
```

**EventBridge Rule (CloudFormation):**
```yaml
DailyReportSchedule:
  Type: AWS::Events::Rule
  Properties:
    Name: daily-report-schedule
    Description: Trigger daily report generation at 9 AM
    ScheduleExpression: cron(0 9 * * ? *)  # 9 AM UTC daily
    State: ENABLED
    Targets:
      - Arn: !GetAtt DailyReportLambda.Arn
        Id: DailyReportTarget

WeeklyReportSchedule:
  Type: AWS::Events::Rule
  Properties:
    Name: weekly-report-schedule
    Description: Trigger weekly report every Monday at 10 AM
    ScheduleExpression: cron(0 10 ? * MON *)  # Monday 10 AM UTC
    State: ENABLED
    Targets:
      - Arn: !GetAtt WeeklyReportLambda.Arn
        Id: WeeklyReportTarget

MonthlyReportSchedule:
  Type: AWS::Events::Rule
  Properties:
    Name: monthly-report-schedule
    Description: Trigger monthly report on 1st at 8 AM
    ScheduleExpression: cron(0 8 1 * ? *)  # 1st of month, 8 AM UTC
    State: ENABLED
    Targets:
      - Arn: !GetAtt MonthlyReportLambda.Arn
        Id: MonthlyReportTarget
```

### 4. GitHub Actions

```yaml
# .github/workflows/daily-report.yml
name: Daily Report

on:
  schedule:
    # Run at 9:00 AM UTC every day
    - cron: '0 9 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  generate-report:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install requests

      - name: Generate and send report
        env:
          ZAPIER_API_URL: ${{ secrets.ZAPIER_API_URL }}
          ZAPIER_API_KEY: ${{ secrets.ZAPIER_API_KEY }}
        run: |
          python scripts/daily_report.py

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: report-logs
          path: logs/
```

## Advanced Patterns

### Dynamic Scheduling

Adjust schedule based on conditions:

```python
import pytz
from datetime import datetime

def should_run_today():
    """Check if report should run today"""
    today = datetime.now(pytz.timezone('America/New_York'))

    # Skip weekends
    if today.weekday() >= 5:
        logger.info("Skipping report (weekend)")
        return False

    # Skip holidays
    holidays = ['2024-12-25', '2024-01-01']
    if today.strftime('%Y-%m-%d') in holidays:
        logger.info("Skipping report (holiday)")
        return False

    return True

def main():
    if not should_run_today():
        return 0

    # Generate and send report
    # ...
```

### Report Variants

Send different reports based on frequency:

```python
def get_report_config(frequency):
    """Get report configuration based on frequency"""
    configs = {
        'hourly': {
            'event_type': 'report.hourly',
            'query_period': timedelta(hours=1),
            'metrics': ['active_users', 'requests_count']
        },
        'daily': {
            'event_type': 'report.daily',
            'query_period': timedelta(days=1),
            'metrics': ['sales', 'orders', 'customers']
        },
        'weekly': {
            'event_type': 'report.weekly',
            'query_period': timedelta(weeks=1),
            'metrics': ['sales', 'orders', 'customers', 'retention']
        },
        'monthly': {
            'event_type': 'report.monthly',
            'query_period': timedelta(days=30),
            'metrics': ['sales', 'orders', 'customers', 'churn', 'mrr']
        }
    }
    return configs[frequency]

def generate_report(frequency='daily'):
    config = get_report_config(frequency)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - config['query_period']

    # Query metrics
    metrics = {}
    for metric in config['metrics']:
        metrics[metric] = query_metric(metric, start_date, end_date)

    return {
        'period': frequency,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'metrics': metrics
    }
```

### Retry Logic

Handle failures with exponential backoff:

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, backoff_factor=2):
    """Decorator for retry with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise

                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)

            raise Exception("Max retries exceeded")

        return wrapper
    return decorator

@retry_with_backoff(max_retries=5, backoff_factor=2)
def send_event_with_retry(token, event_data):
    """Send event with automatic retry"""
    return send_event(token, event_data)
```

## Monitoring

### CloudWatch Alarms

```python
# Create CloudWatch alarm for failed reports
import boto3

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_alarm(
    AlarmName='DailyReportFailures',
    AlarmDescription='Alert when daily report fails',
    ActionsEnabled=True,
    AlarmActions=[
        'arn:aws:sns:us-east-2:123456789:alerts'
    ],
    MetricName='DailyReportFailure',
    Namespace='ScheduledJobs',
    Statistic='Sum',
    Period=300,  # 5 minutes
    EvaluationPeriods=1,
    Threshold=1,
    ComparisonOperator='GreaterThanOrEqualToThreshold'
)
```

### Success/Failure Tracking

```python
import json
from pathlib import Path

def track_execution(status, event_id=None, error=None):
    """Track execution history"""
    log_file = Path('/var/log/scheduled_jobs/history.jsonl')
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        'timestamp': datetime.now().isoformat(),
        'status': status,
        'event_id': event_id,
        'error': str(error) if error else None
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def main():
    try:
        # Generate and send report
        result = send_event(token, report_data)
        track_execution('success', result['id'])

    except Exception as e:
        track_execution('failure', error=e)
        raise
```

## Testing

### Test Locally

```bash
# Set test environment
export ZAPIER_API_URL="https://dev-api.lambda-url.us-east-2.on.aws"
export ZAPIER_API_KEY="test-key"

# Run script manually
python daily_report.py
```

### Test Lambda Function

```bash
# Invoke Lambda with test event
aws lambda invoke \
  --function-name DailyReportLambda \
  --payload '{"test": true}' \
  --log-type Tail \
  response.json

# View response
cat response.json | jq
```

### Dry Run Mode

```python
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'

def send_event(token, event_data):
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would send event: {event_data}")
        return {
            'id': 'dry-run-event-id',
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }

    # Actually send event
    response = requests.post(...)
    return response.json()
```

## Best Practices

1. **Idempotency** - Use unique identifiers to prevent duplicate processing
2. **Error Handling** - Always implement retry logic with backoff
3. **Logging** - Log all executions (success and failure)
4. **Monitoring** - Set up alerts for failures
5. **Testing** - Test schedules with dry-run mode
6. **Timezone Awareness** - Use UTC or explicit timezones
7. **Resource Cleanup** - Clean up temporary files after execution
8. **Documentation** - Document schedule and expected behavior

## Common Issues

### Cron Not Running

```bash
# Check cron service
systemctl status cron  # Ubuntu/Debian
systemctl status crond  # CentOS/RHEL

# View cron logs
grep CRON /var/log/syslog  # Ubuntu/Debian
grep CRON /var/log/cron    # CentOS/RHEL

# Test script manually
/path/to/script.sh
```

### Lambda Timeout

Increase Lambda timeout in CloudFormation:

```yaml
DailyReportLambda:
  Type: AWS::Lambda::Function
  Properties:
    Timeout: 300  # 5 minutes (max 15 minutes)
    MemorySize: 1024
```

### Rate Limiting

Spread scheduled events to avoid overwhelming API:

```python
import random
import time

# Add random delay (0-60 seconds)
delay = random.randint(0, 60)
logger.info(f"Waiting {delay}s before execution")
time.sleep(delay)
```

## Next Steps

- See [webhook-bridge.md](./webhook-bridge.md) for webhook forwarding
- See [database-sync.md](./database-sync.md) for database change tracking
- Read [Developer Guide](../../docs/DEVELOPER_GUIDE.md) for more patterns
