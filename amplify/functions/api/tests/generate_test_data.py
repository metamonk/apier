"""
Test Data Generation Script for Metrics Endpoints (Task 23.4)

This script provides utilities to generate realistic test data for the metrics
endpoints. It creates events with various statuses, timestamps, latencies, and
error scenarios to enable comprehensive testing.

Usage:
    # In your test file:
    from tests.generate_test_data import EventDataGenerator

    generator = EventDataGenerator(dynamodb_table)

    # Generate default dataset (mixed statuses)
    events = generator.generate_realistic_dataset(count=500)

    # Generate specific scenarios
    generator.generate_high_failure_scenario(delivered=20, failed=80)
    generator.generate_latency_test_dataset(latencies=[1, 5, 10, 30, 60])
    generator.generate_throughput_dataset(events_per_hour=10, hours=24)

Features:
    - Realistic event distribution (85% delivered, 10% pending, 5% failed)
    - Time-distributed events for throughput testing
    - Controlled latency values for percentile testing
    - Various error scenarios (high/low failure rates)
    - Configurable event types, sources, and timestamps
    - Support for GSI testing (status-lastAttemptAt-index)
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Literal
from decimal import Decimal
import random


class EventDataGenerator:
    """
    Generate realistic test data for metrics endpoint testing.

    This class provides methods to create DynamoDB event items with various
    characteristics for testing different metrics scenarios.
    """

    # Realistic event types for test data
    EVENT_TYPES = [
        "user.signup",
        "user.login",
        "user.logout",
        "order.placed",
        "order.completed",
        "order.cancelled",
        "payment.success",
        "payment.failed",
        "webhook.error",
        "data.sync",
        "email.queue",
        "analytics.track",
        "notification.sent",
    ]

    # Realistic event sources
    EVENT_SOURCES = [
        "web",
        "mobile",
        "api",
        "cron",
        "stripe",
        "mailer",
        "admin",
    ]

    def __init__(self, dynamodb_table):
        """
        Initialize the generator with a DynamoDB table reference.

        Args:
            dynamodb_table: boto3 DynamoDB table resource for inserting events
        """
        self.table = dynamodb_table
        self.event_counter = 0

    def _generate_event_id(self, prefix: str = "test") -> str:
        """Generate a unique event ID."""
        self.event_counter += 1
        return f"{prefix}-{self.event_counter}-{uuid.uuid4().hex[:8]}"

    def _generate_payload(self, event_type: str) -> Dict[str, Any]:
        """Generate realistic payload based on event type."""
        base_payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "environment": "test",
        }

        if "user" in event_type:
            base_payload.update({
                "user_id": f"user_{random.randint(1000, 9999)}",
                "email": f"test{random.randint(100, 999)}@example.com",
            })
        elif "order" in event_type:
            base_payload.update({
                "order_id": f"order_{random.randint(10000, 99999)}",
                "amount": str(round(random.uniform(10.0, 500.0), 2)),  # Convert to string
                "currency": "USD",
            })
        elif "payment" in event_type:
            base_payload.update({
                "payment_id": f"pay_{random.randint(10000, 99999)}",
                "amount": str(round(random.uniform(10.0, 500.0), 2)),  # Convert to string
                "method": random.choice(["card", "paypal", "bank"]),
            })

        return base_payload

    def create_event(
        self,
        status: Literal["pending", "delivered", "failed"],
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        latency_seconds: Optional[float] = None,
        event_type: Optional[str] = None,
        event_source: Optional[str] = None,
        delivery_attempts: Optional[int] = None,
        error_message: Optional[str] = None,
        event_id: Optional[str] = None,
        last_attempt_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a single event with specified characteristics.

        Args:
            status: Event status (pending, delivered, failed)
            created_at: Event creation timestamp (default: now)
            updated_at: Last update timestamp (default: created_at or created_at + latency)
            latency_seconds: Time between creation and completion (for delivered/failed)
            event_type: Type of event (default: random from EVENT_TYPES)
            event_source: Source of event (default: random from EVENT_SOURCES)
            delivery_attempts: Number of delivery attempts (default: auto-calculated)
            error_message: Error message for failed events
            event_id: Custom event ID (default: auto-generated)
            last_attempt_at: Last delivery attempt timestamp for GSI

        Returns:
            Dict containing DynamoDB event item
        """
        now = datetime.utcnow()
        created_at = created_at or now

        # Calculate updated_at based on status and latency
        if updated_at is None:
            if latency_seconds is not None:
                updated_at = created_at + timedelta(seconds=latency_seconds)
            elif status in ["delivered", "failed"]:
                # Default latency for completed events
                default_latency = random.uniform(1, 60) if status == "delivered" else random.uniform(60, 300)
                updated_at = created_at + timedelta(seconds=default_latency)
            else:
                updated_at = created_at

        # Set delivery attempts based on status
        if delivery_attempts is None:
            if status == "pending":
                delivery_attempts = 0
            elif status == "delivered":
                delivery_attempts = random.choice([1, 1, 1, 2])  # Mostly 1, sometimes 2
            else:  # failed
                delivery_attempts = 3

        # Generate event details
        event_type = event_type or random.choice(self.EVENT_TYPES)
        event_source = event_source or random.choice(self.EVENT_SOURCES)
        event_id = event_id or self._generate_event_id(status)

        event = {
            "id": event_id,
            "type": event_type,
            "source": event_source,
            "status": status,
            "created_at": created_at.isoformat() + "Z",
            "updated_at": updated_at.isoformat() + "Z",
            "payload": self._generate_payload(event_type),
            "delivery_attempts": delivery_attempts,
            "ttl": int((now + timedelta(days=90)).timestamp()),
        }

        # Add optional fields
        if error_message and status == "failed":
            event["error_message"] = error_message

        if last_attempt_at:
            event["last_attempt_at"] = last_attempt_at
        elif status in ["delivered", "failed"]:
            event["last_attempt_at"] = updated_at.isoformat() + "Z"

        return event

    def bulk_insert_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert multiple events into DynamoDB.

        Args:
            events: List of event dictionaries to insert

        Returns:
            List of inserted events
        """
        for event in events:
            self.table.put_item(Item=event)
        return events

    # ========================================================================
    # Preset Generators for Common Scenarios
    # ========================================================================

    def generate_realistic_dataset(
        self,
        count: int = 500,
        hours_ago_range: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Generate a realistic dataset with typical distribution.

        Distribution:
        - 85% delivered
        - 10% pending
        - 5% failed

        Args:
            count: Total number of events to generate
            hours_ago_range: Spread events across this many hours (default: 12)

        Returns:
            List of generated events
        """
        now = datetime.utcnow()
        events = []

        delivered_count = int(count * 0.85)
        pending_count = int(count * 0.10)
        failed_count = count - delivered_count - pending_count

        # Generate delivered events
        for i in range(delivered_count):
            hours_ago = (i % (hours_ago_range * 2)) * 0.5
            created_time = now - timedelta(hours=hours_ago)
            latency = random.uniform(1, 60)  # 1-60 seconds latency

            event = self.create_event(
                status="delivered",
                created_at=created_time,
                latency_seconds=latency,
            )
            events.append(event)

        # Generate pending events
        for i in range(pending_count):
            hours_ago = random.uniform(0, hours_ago_range)
            created_time = now - timedelta(hours=hours_ago)

            event = self.create_event(
                status="pending",
                created_at=created_time,
            )
            events.append(event)

        # Generate failed events
        for i in range(failed_count):
            hours_ago = random.uniform(0, hours_ago_range)
            created_time = now - timedelta(hours=hours_ago)
            latency = random.uniform(60, 300)  # Failures take longer

            error_messages = [
                "Webhook endpoint returned 500",
                "Connection timeout",
                "Webhook endpoint returned 404",
                "Max retries exceeded",
                "Invalid response format",
            ]

            event = self.create_event(
                status="failed",
                created_at=created_time,
                latency_seconds=latency,
                error_message=random.choice(error_messages),
            )
            events.append(event)

        return self.bulk_insert_events(events)

    def generate_high_failure_scenario(
        self,
        delivered: int = 20,
        failed: int = 80,
        pending: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Generate a high-failure scenario for testing error metrics.

        Args:
            delivered: Number of delivered events
            failed: Number of failed events
            pending: Number of pending events

        Returns:
            List of generated events
        """
        now = datetime.utcnow()
        events = []

        # Delivered events
        for i in range(delivered):
            event = self.create_event(
                status="delivered",
                created_at=now - timedelta(minutes=random.randint(1, 60)),
            )
            events.append(event)

        # Failed events with various error types
        error_types = [
            "Webhook endpoint returned 500",
            "Connection timeout",
            "Webhook endpoint returned 503",
            "Rate limit exceeded",
            "Invalid webhook URL",
        ]

        for i in range(failed):
            event = self.create_event(
                status="failed",
                created_at=now - timedelta(minutes=random.randint(1, 120)),
                error_message=error_types[i % len(error_types)],
            )
            events.append(event)

        # Pending events
        for i in range(pending):
            event = self.create_event(
                status="pending",
                created_at=now - timedelta(minutes=random.randint(1, 30)),
            )
            events.append(event)

        return self.bulk_insert_events(events)

    def generate_latency_test_dataset(
        self,
        latencies: List[float],
        status: Literal["delivered", "failed"] = "delivered",
    ) -> List[Dict[str, Any]]:
        """
        Generate events with specific latencies for percentile testing.

        Args:
            latencies: List of latency values in seconds
            status: Status for the events (delivered or failed)

        Returns:
            List of generated events
        """
        now = datetime.utcnow()
        events = []

        for i, latency_seconds in enumerate(latencies):
            created_time = now - timedelta(seconds=latency_seconds)

            event = self.create_event(
                status=status,
                created_at=created_time,
                updated_at=now,
                latency_seconds=latency_seconds,
                event_id=f"latency-test-{i}",
            )
            events.append(event)

        return self.bulk_insert_events(events)

    def generate_throughput_dataset(
        self,
        events_per_hour: int = 10,
        hours: int = 24,
        include_old_events: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Generate time-distributed events for throughput testing.

        Args:
            events_per_hour: Number of events to generate per hour
            hours: Number of hours to distribute events across
            include_old_events: If True, also generate events >24h old

        Returns:
            List of generated events
        """
        now = datetime.utcnow()
        events = []

        total_events = events_per_hour * hours

        # Generate recent events (within specified hours)
        for i in range(total_events):
            hours_ago = (i / events_per_hour)
            created_time = now - timedelta(hours=hours_ago)

            status = random.choice(["delivered", "delivered", "delivered", "pending", "failed"])

            event = self.create_event(
                status=status,
                created_at=created_time,
            )
            events.append(event)

        # Generate old events (for testing time filtering)
        if include_old_events:
            for i in range(events_per_hour * 5):  # 5 hours worth of old events
                hours_ago = 25 + (i / events_per_hour)  # Start at 25h ago
                created_time = now - timedelta(hours=hours_ago)

                event = self.create_event(
                    status="delivered",
                    created_at=created_time,
                )
                events.append(event)

        return self.bulk_insert_events(events)

    def generate_empty_state(self) -> List[Dict[str, Any]]:
        """
        Generate an empty dataset (no events).

        Returns:
            Empty list
        """
        return []

    def generate_single_event(
        self,
        status: Literal["pending", "delivered", "failed"] = "delivered",
        latency_seconds: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """
        Generate a single event for minimal testing.

        Args:
            status: Event status
            latency_seconds: Latency for the event

        Returns:
            List containing one event
        """
        now = datetime.utcnow()
        created_time = now - timedelta(seconds=latency_seconds)

        event = self.create_event(
            status=status,
            created_at=created_time,
            updated_at=now,
            latency_seconds=latency_seconds,
        )

        return self.bulk_insert_events([event])

    def generate_large_dataset(
        self,
        count: int = 2000,
        delivered_pct: float = 0.80,
        pending_pct: float = 0.10,
        failed_pct: float = 0.10,
    ) -> List[Dict[str, Any]]:
        """
        Generate a large dataset for load testing.

        Args:
            count: Total number of events
            delivered_pct: Percentage of delivered events (0.0-1.0)
            pending_pct: Percentage of pending events (0.0-1.0)
            failed_pct: Percentage of failed events (0.0-1.0)

        Returns:
            List of generated events
        """
        now = datetime.utcnow()
        events = []

        delivered_count = int(count * delivered_pct)
        pending_count = int(count * pending_pct)
        failed_count = int(count * failed_pct)

        # Adjust for rounding
        total = delivered_count + pending_count + failed_count
        if total < count:
            delivered_count += (count - total)

        # Generate in batches to avoid memory issues
        batch_size = 500

        # Delivered events
        for i in range(delivered_count):
            hours_ago = (i % 48) * 0.5
            created_time = now - timedelta(hours=hours_ago)

            event = self.create_event(
                status="delivered",
                created_at=created_time,
            )
            events.append(event)

            # Insert in batches
            if len(events) >= batch_size:
                self.bulk_insert_events(events)
                events = []

        # Pending events
        for i in range(pending_count):
            hours_ago = random.uniform(0, 24)
            created_time = now - timedelta(hours=hours_ago)

            event = self.create_event(
                status="pending",
                created_at=created_time,
            )
            events.append(event)

            if len(events) >= batch_size:
                self.bulk_insert_events(events)
                events = []

        # Failed events
        for i in range(failed_count):
            hours_ago = random.uniform(0, 24)
            created_time = now - timedelta(hours=hours_ago)

            event = self.create_event(
                status="failed",
                created_at=created_time,
            )
            events.append(event)

            if len(events) >= batch_size:
                self.bulk_insert_events(events)
                events = []

        # Insert remaining events
        if events:
            self.bulk_insert_events(events)

        return []  # Return empty to save memory

    def generate_percentile_test_dataset(
        self,
        count: int = 100,
        min_latency: float = 1.0,
        max_latency: float = 100.0,
    ) -> List[Dict[str, Any]]:
        """
        Generate events with evenly distributed latencies for percentile testing.

        Args:
            count: Number of events to generate
            min_latency: Minimum latency in seconds
            max_latency: Maximum latency in seconds

        Returns:
            List of generated events
        """
        latencies = []
        step = (max_latency - min_latency) / count

        for i in range(count):
            latency = min_latency + (i * step)
            latencies.append(latency)

        return self.generate_latency_test_dataset(latencies)

    def generate_gsi_test_dataset(
        self,
        count_per_status: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Generate events optimized for GSI (status-lastAttemptAt-index) testing.

        Args:
            count_per_status: Number of events per status type

        Returns:
            List of generated events
        """
        now = datetime.utcnow()
        events = []

        statuses = ["pending", "delivered", "failed"]

        for status in statuses:
            for i in range(count_per_status):
                hours_ago = random.uniform(0, 48)
                created_time = now - timedelta(hours=hours_ago)

                # For delivered/failed, set last_attempt_at
                last_attempt = None
                if status in ["delivered", "failed"]:
                    attempt_time = created_time + timedelta(seconds=random.uniform(1, 300))
                    last_attempt = attempt_time.isoformat() + "Z"

                event = self.create_event(
                    status=status,
                    created_at=created_time,
                    last_attempt_at=last_attempt,
                )
                events.append(event)

        return self.bulk_insert_events(events)


# ============================================================================
# Convenience Functions for Quick Usage
# ============================================================================

def quick_realistic_data(dynamodb_table, count: int = 500):
    """Quick function to generate realistic test data."""
    generator = EventDataGenerator(dynamodb_table)
    return generator.generate_realistic_dataset(count=count)


def quick_high_failure_data(dynamodb_table, delivered: int = 20, failed: int = 80):
    """Quick function to generate high-failure scenario."""
    generator = EventDataGenerator(dynamodb_table)
    return generator.generate_high_failure_scenario(delivered=delivered, failed=failed)


def quick_latency_data(dynamodb_table, latencies: List[float]):
    """Quick function to generate latency test data."""
    generator = EventDataGenerator(dynamodb_table)
    return generator.generate_latency_test_dataset(latencies=latencies)


def quick_throughput_data(dynamodb_table, events_per_hour: int = 10, hours: int = 24):
    """Quick function to generate throughput test data."""
    generator = EventDataGenerator(dynamodb_table)
    return generator.generate_throughput_dataset(events_per_hour=events_per_hour, hours=hours)


# ============================================================================
# Example Usage for Reference
# ============================================================================

if __name__ == "__main__":
    """
    Example usage (for reference only - not meant to be run directly).

    In your test files, import and use like:

        from tests.generate_test_data import EventDataGenerator

        @pytest.fixture
        def sample_events(dynamodb_table):
            generator = EventDataGenerator(dynamodb_table)
            return generator.generate_realistic_dataset(count=500)
    """
    print("This is a utility module. Import it in your test files.")
    print("\nExample usage:")
    print("  from tests.generate_test_data import EventDataGenerator")
    print("  generator = EventDataGenerator(dynamodb_table)")
    print("  events = generator.generate_realistic_dataset(count=500)")
