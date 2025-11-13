# Database Sync Pattern

Track database changes and trigger Zapier workflows automatically.

## Overview

```
Database Change → ORM Signal/Trigger → Zapier Triggers API → Zapier Workflows
  (User Signup)     (Django/Rails)
```

## Why Use This Pattern?

**Benefits:**
- **Real-time Notifications** - Trigger workflows immediately on data changes
- **Decoupled Architecture** - Database logic separate from workflow logic
- **Flexible Workflows** - Change workflows without changing database code
- **Reliable Delivery** - Events buffered until Zapier acknowledges
- **Historical Tracking** - All changes logged in DynamoDB

**Use Cases:**
- User registration/profile updates
- Order status changes
- Inventory updates
- Payment confirmations
- Document approvals

## Implementation

### Django (Python)

#### 1. Using Django Signals

```python
# myapp/signals.py
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from myapp.models import User, Order
from myapp.tasks import send_zapier_event
import os

ZAPIER_API_URL = os.environ.get("ZAPIER_API_URL")
ZAPIER_API_TOKEN = os.environ.get("ZAPIER_API_TOKEN")

@receiver(post_save, sender=User)
def user_saved_handler(sender, instance, created, **kwargs):
    """
    Trigger Zapier event when user is created or updated
    """
    if created:
        # User was just created
        event_type = "user.created"
        payload = {
            "user_id": str(instance.id),
            "email": instance.email,
            "username": instance.username,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "created_at": instance.date_joined.isoformat()
        }
    else:
        # User was updated
        event_type = "user.updated"
        payload = {
            "user_id": str(instance.id),
            "email": instance.email,
            "username": instance.username,
            "updated_at": instance.last_login.isoformat() if instance.last_login else None
        }

    # Send event asynchronously (Celery task)
    send_zapier_event.delay(
        event_type=event_type,
        source="django-app",
        payload=payload
    )

@receiver(post_save, sender=Order)
def order_saved_handler(sender, instance, created, **kwargs):
    """
    Trigger Zapier event when order status changes
    """
    if created:
        event_type = "order.placed"
    elif instance.status == "shipped":
        event_type = "order.shipped"
    elif instance.status == "delivered":
        event_type = "order.delivered"
    elif instance.status == "cancelled":
        event_type = "order.cancelled"
    else:
        # Don't send event for other status changes
        return

    payload = {
        "order_id": str(instance.id),
        "user_id": str(instance.user_id),
        "status": instance.status,
        "total": float(instance.total),
        "items_count": instance.items.count(),
        "updated_at": instance.updated_at.isoformat()
    }

    send_zapier_event.delay(
        event_type=event_type,
        source="django-app",
        payload=payload
    )

@receiver(pre_delete, sender=User)
def user_deleted_handler(sender, instance, **kwargs):
    """
    Trigger Zapier event before user is deleted
    """
    send_zapier_event.delay(
        event_type="user.deleted",
        source="django-app",
        payload={
            "user_id": str(instance.id),
            "email": instance.email,
            "username": instance.username,
            "deleted_at": datetime.now().isoformat()
        }
    )
```

#### 2. Celery Task for Asynchronous Sending

```python
# myapp/tasks.py
from celery import shared_task
import requests
import os

ZAPIER_API_URL = os.environ.get("ZAPIER_API_URL")
ZAPIER_API_TOKEN = os.environ.get("ZAPIER_API_TOKEN")

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_zapier_event(self, event_type, source, payload):
    """
    Send event to Zapier Triggers API with automatic retries
    """
    try:
        response = requests.post(
            f"{ZAPIER_API_URL}/events",
            headers={
                "Authorization": f"Bearer {ZAPIER_API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "type": event_type,
                "source": source,
                "payload": payload
            },
            timeout=5
        )

        response.raise_for_status()

        return {
            "success": True,
            "event_id": response.json()["id"]
        }

    except requests.exceptions.RequestException as exc:
        # Retry on failure
        raise self.retry(exc=exc)
```

#### 3. Register Signals

```python
# myapp/apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    def ready(self):
        import myapp.signals  # Register signals
```

```python
# myapp/__init__.py
default_app_config = 'myapp.apps.MyAppConfig'
```

### Ruby on Rails

#### 1. Using Active Record Callbacks

```ruby
# app/models/user.rb
class User < ApplicationRecord
  after_create :notify_zapier_created
  after_update :notify_zapier_updated
  after_destroy :notify_zapier_deleted

  private

  def notify_zapier_created
    ZapierEventJob.perform_later(
      event_type: 'user.created',
      source: 'rails-app',
      payload: {
        user_id: id,
        email: email,
        username: username,
        created_at: created_at.iso8601
      }
    )
  end

  def notify_zapier_updated
    # Only notify if important fields changed
    return unless saved_changes?

    changed_fields = saved_changes.keys

    ZapierEventJob.perform_later(
      event_type: 'user.updated',
      source: 'rails-app',
      payload: {
        user_id: id,
        email: email,
        username: username,
        changed_fields: changed_fields,
        updated_at: updated_at.iso8601
      }
    )
  end

  def notify_zapier_deleted
    ZapierEventJob.perform_later(
      event_type: 'user.deleted',
      source: 'rails-app',
      payload: {
        user_id: id,
        email: email,
        username: username,
        deleted_at: Time.current.iso8601
      }
    )
  end
end
```

#### 2. Background Job

```ruby
# app/jobs/zapier_event_job.rb
class ZapierEventJob < ApplicationJob
  queue_as :default
  retry_on RequestException, wait: 1.minute, attempts: 3

  def perform(event_type:, source:, payload:)
    api_url = ENV['ZAPIER_API_URL']
    api_token = ENV['ZAPIER_API_TOKEN']

    response = HTTParty.post(
      "#{api_url}/events",
      headers: {
        'Authorization' => "Bearer #{api_token}",
        'Content-Type' => 'application/json'
      },
      body: {
        type: event_type,
        source: source,
        payload: payload
      }.to_json,
      timeout: 5
    )

    unless response.success?
      raise RequestException, "Failed to send event: #{response.code}"
    end

    Rails.logger.info "Sent Zapier event: #{event_type} (#{response['id']})"
  end
end
```

### Node.js (Sequelize)

```javascript
// models/user.js
const { Sequelize, DataTypes } = require('sequelize');
const sendZapierEvent = require('../services/zapier');

module.exports = (sequelize) => {
  const User = sequelize.define('User', {
    id: {
      type: DataTypes.UUID,
      defaultValue: Sequelize.UUIDV4,
      primaryKey: true
    },
    email: {
      type: DataTypes.STRING,
      allowNull: false,
      unique: true
    },
    username: DataTypes.STRING,
    firstName: DataTypes.STRING,
    lastName: DataTypes.STRING
  });

  // After create hook
  User.afterCreate(async (user, options) => {
    await sendZapierEvent({
      type: 'user.created',
      source: 'node-app',
      payload: {
        user_id: user.id,
        email: user.email,
        username: user.username,
        first_name: user.firstName,
        last_name: user.lastName,
        created_at: user.createdAt.toISOString()
      }
    });
  });

  // After update hook
  User.afterUpdate(async (user, options) => {
    // Get changed fields
    const changedFields = Object.keys(user._changed);

    if (changedFields.length > 0) {
      await sendZapierEvent({
        type: 'user.updated',
        source: 'node-app',
        payload: {
          user_id: user.id,
          email: user.email,
          username: user.username,
          changed_fields: changedFields,
          updated_at: user.updatedAt.toISOString()
        }
      });
    }
  });

  // After destroy hook
  User.afterDestroy(async (user, options) => {
    await sendZapierEvent({
      type: 'user.deleted',
      source: 'node-app',
      payload: {
        user_id: user.id,
        email: user.email,
        username: user.username,
        deleted_at: new Date().toISOString()
      }
    });
  });

  return User;
};
```

```javascript
// services/zapier.js
const axios = require('axios');

const ZAPIER_API_URL = process.env.ZAPIER_API_URL;
const ZAPIER_API_TOKEN = process.env.ZAPIER_API_TOKEN;

async function sendZapierEvent(eventData) {
  try {
    const response = await axios.post(
      `${ZAPIER_API_URL}/events`,
      eventData,
      {
        headers: {
          'Authorization': `Bearer ${ZAPIER_API_TOKEN}`,
          'Content-Type': 'application/json'
        },
        timeout: 5000
      }
    );

    console.log(`Sent Zapier event: ${eventData.type} (${response.data.id})`);
    return response.data;

  } catch (error) {
    console.error('Failed to send Zapier event:', error.message);

    // Re-throw to trigger retry in caller
    throw error;
  }
}

module.exports = sendZapierEvent;
```

## Database Triggers (PostgreSQL)

For framework-agnostic approach, use database triggers:

```sql
-- Create function to call HTTP endpoint
CREATE OR REPLACE FUNCTION notify_zapier()
RETURNS trigger AS $$
DECLARE
    event_type text;
    payload json;
BEGIN
    -- Determine event type
    IF (TG_OP = 'INSERT') THEN
        event_type := TG_TABLE_NAME || '.created';
        payload := row_to_json(NEW);
    ELSIF (TG_OP = 'UPDATE') THEN
        event_type := TG_TABLE_NAME || '.updated';
        payload := row_to_json(NEW);
    ELSIF (TG_OP = 'DELETE') THEN
        event_type := TG_TABLE_NAME || '.deleted';
        payload := row_to_json(OLD);
    END IF;

    -- Send HTTP request (requires pg_net extension or external function)
    PERFORM net.http_post(
        url := 'https://your-webhook-processor.com/postgres-trigger',
        headers := '{"Content-Type": "application/json"}'::jsonb,
        body := json_build_object(
            'event_type', event_type,
            'source', 'postgres-trigger',
            'payload', payload
        )::text
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on users table
CREATE TRIGGER users_zapier_trigger
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW
EXECUTE FUNCTION notify_zapier();
```

**Note:** PostgreSQL HTTP requests require extensions like `pg_net` or external functions. For production, use application-level hooks instead.

## Best Practices

### 1. Selective Event Generation

Only send events for meaningful changes:

```python
@receiver(post_save, sender=User)
def user_saved_handler(sender, instance, created, update_fields, **kwargs):
    # Skip if only last_login was updated
    if not created and update_fields and update_fields == {'last_login'}:
        return

    # Only send events for important field changes
    important_fields = {'email', 'username', 'status'}

    if not created:
        changed_fields = set(update_fields or [])
        if not changed_fields & important_fields:
            return  # No important fields changed

    # Send event...
```

### 2. Include Context

Provide enough data for downstream workflows:

```python
payload = {
    "user_id": str(instance.id),
    "email": instance.email,
    "username": instance.username,

    # Include related data
    "account_type": instance.account.type,
    "subscription_plan": instance.subscription.plan,

    # Include metadata
    "environment": os.environ.get("ENVIRONMENT", "production"),
    "app_version": "1.0.0",

    # Include timestamps
    "event_timestamp": datetime.now().isoformat(),
    "entity_created_at": instance.created_at.isoformat(),
    "entity_updated_at": instance.updated_at.isoformat()
}
```

### 3. Handle Bulk Operations

Avoid overwhelming the API during bulk operations:

```python
from django.db import transaction

# Disable signals during bulk operations
@transaction.atomic
def bulk_update_users():
    with transaction.atomic():
        # Temporarily disable signals
        from django.db.models.signals import post_save
        post_save.disconnect(user_saved_handler, sender=User)

        # Perform bulk operation
        User.objects.filter(status='pending').update(status='active')

        # Re-enable signals
        post_save.connect(user_saved_handler, sender=User)

        # Send single batch event
        send_zapier_event.delay(
            event_type="users.bulk_updated",
            source="django-app",
            payload={
                "count": updated_count,
                "status": "active",
                "timestamp": datetime.now().isoformat()
            }
        )
```

### 4. Error Handling

Implement retry logic with exponential backoff:

```python
@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,  # 1 minute
    retry_backoff=True,      # Exponential backoff
    retry_backoff_max=600,   # Max 10 minutes
    retry_jitter=True        # Add randomness to prevent thundering herd
)
def send_zapier_event(self, event_type, source, payload):
    try:
        response = requests.post(...)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code >= 500:
            # Retry on server errors
            raise self.retry(exc=exc)
        else:
            # Don't retry on client errors (400-499)
            raise

    except requests.exceptions.RequestException as exc:
        # Retry on network errors
        raise self.retry(exc=exc)
```

### 5. Testing

Mock Zapier API in tests:

```python
# tests/test_signals.py
from unittest.mock import patch, Mock
from myapp.models import User

class TestUserSignals(TestCase):
    @patch('myapp.tasks.send_zapier_event.delay')
    def test_user_created_sends_event(self, mock_send_event):
        # Create user
        user = User.objects.create(
            username='testuser',
            email='test@example.com'
        )

        # Verify event was sent
        mock_send_event.assert_called_once_with(
            event_type='user.created',
            source='django-app',
            payload={
                'user_id': str(user.id),
                'email': 'test@example.com',
                'username': 'testuser',
                'created_at': user.date_joined.isoformat()
            }
        )
```

## Monitoring

### Track Event Generation

```python
import logging
from prometheus_client import Counter

logger = logging.getLogger(__name__)

events_sent = Counter(
    'zapier_events_sent_total',
    'Total Zapier events sent',
    ['event_type', 'source']
)

events_failed = Counter(
    'zapier_events_failed_total',
    'Total failed Zapier events',
    ['event_type', 'source', 'error']
)

@shared_task
def send_zapier_event(event_type, source, payload):
    try:
        response = requests.post(...)
        response.raise_for_status()

        events_sent.labels(
            event_type=event_type,
            source=source
        ).inc()

        logger.info(f"Sent Zapier event: {event_type}")
        return response.json()

    except Exception as e:
        events_failed.labels(
            event_type=event_type,
            source=source,
            error=type(e).__name__
        ).inc()

        logger.error(f"Failed to send Zapier event: {event_type} - {str(e)}")
        raise
```

## Common Patterns

### Change Tracking

Track what changed in updates:

```python
@receiver(post_save, sender=User)
def user_saved_handler(sender, instance, created, **kwargs):
    if not created:
        # Get previous values from database
        try:
            old_instance = User.objects.get(pk=instance.pk)
        except User.DoesNotExist:
            return

        # Compare old and new
        changes = {}
        for field in ['email', 'username', 'status']:
            old_value = getattr(old_instance, field)
            new_value = getattr(instance, field)

            if old_value != new_value:
                changes[field] = {
                    'old': old_value,
                    'new': new_value
                }

        if changes:
            send_zapier_event.delay(
                event_type="user.updated",
                source="django-app",
                payload={
                    "user_id": str(instance.id),
                    "changes": changes,
                    "updated_at": instance.updated_at.isoformat()
                }
            )
```

### Conditional Events

Send different events based on field values:

```python
@receiver(post_save, sender=Order)
def order_status_changed(sender, instance, created, **kwargs):
    if created:
        event_type = "order.created"
    else:
        # Map status to event type
        status_events = {
            'paid': 'order.paid',
            'shipped': 'order.shipped',
            'delivered': 'order.delivered',
            'cancelled': 'order.cancelled',
            'refunded': 'order.refunded'
        }

        event_type = status_events.get(instance.status)

        if not event_type:
            return  # Don't send event for other statuses

    send_zapier_event.delay(
        event_type=event_type,
        source="django-app",
        payload={
            "order_id": str(instance.id),
            "status": instance.status,
            "total": float(instance.total)
        }
    )
```

## Next Steps

- See [webhook-bridge.md](./webhook-bridge.md) for webhook forwarding
- See [scheduled-events.md](./scheduled-events.md) for periodic events
- Read [Developer Guide](../../docs/DEVELOPER_GUIDE.md) for more patterns
