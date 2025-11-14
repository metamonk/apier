#!/usr/bin/env python3
"""
UAT Environment Setup Script

This script prepares the sandbox environment for User Acceptance Testing by:
1. Connecting to the sandbox DynamoDB table
2. Clearing existing test data (optional)
3. Generating realistic test datasets using the test data generators
4. Verifying the data was loaded successfully

Usage:
    python setup_uat_environment.py [--clear] [--scenario SCENARIO]

Options:
    --clear: Clear all existing data before generating new data
    --scenario: Specific test scenario to set up (default: all)
                Options: realistic, failures, latency, throughput, all
"""

import argparse
import boto3
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path to import test data generator
sys.path.insert(0, os.path.dirname(__file__))
from generate_test_data import TestDataGenerator


# Sandbox environment configuration
SANDBOX_CONFIG = {
    "region": "us-east-2",
    "table_name": "Events-amplify-dmmfqlsr845yz-sandbox-branch-f5abe847e1-apistack7B433BC7-15JGQL7OVS2TI",
    "api_url": "https://vwjsgmo7i5ooweeep6vshc7djy0btmai.lambda-url.us-east-2.on.aws",
    "dashboard_url": "https://sandbox.dmmfqlsr845yz.amplifyapp.com",
}


def clear_table(table) -> int:
    """
    Clear all items from the DynamoDB table.

    Args:
        table: DynamoDB table resource

    Returns:
        Number of items deleted
    """
    print("⚠️  Clearing existing data from sandbox environment...")

    # Scan all items
    response = table.scan()
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    # Delete all items
    deleted_count = 0
    for item in items:
        table.delete_item(
            Key={
                "id": item["id"],
                "created_at": item["created_at"]
            }
        )
        deleted_count += 1

    print(f"✅ Cleared {deleted_count} items from sandbox environment")
    return deleted_count


def setup_realistic_scenario(generator: TestDataGenerator) -> int:
    """
    Set up realistic dataset for general testing.

    Scenario: DO-1, DO-2, AS-3, AS-4 (Dashboard viewing, event filtering)
    - 100 events with realistic distribution
    - 85% delivered, 10% pending, 5% failed
    - Distributed over last 12 hours

    Returns:
        Number of events generated
    """
    print("\n📦 Setting up REALISTIC scenario (100 events)...")
    events = generator.generate_realistic_dataset(count=100, hours_ago_range=12)
    print(f"   ✅ Generated {len(events)} realistic events")
    return len(events)


def setup_failure_scenario(generator: TestDataGenerator) -> int:
    """
    Set up high failure scenario for error analytics testing.

    Scenario: DO-5 (Error analytics and top errors)
    - 110 events with elevated failure rate
    - 20 delivered, 80 failed, 10 pending
    - Tests error rate calculations and error message display

    Returns:
        Number of events generated
    """
    print("\n📦 Setting up FAILURE scenario (110 events)...")
    events = generator.generate_high_failure_scenario(
        delivered=20,
        failed=80,
        pending=10
    )
    print(f"   ✅ Generated {len(events)} events with 80% failure rate")
    return len(events)


def setup_latency_scenario(generator: TestDataGenerator) -> int:
    """
    Set up latency test dataset for percentile validation.

    Scenario: DO-3 (Latency metrics validation)
    - 100 events with uniform latency distribution 1.0s - 10.0s
    - Expected P50: ~5.5s, P95: ~9.5s, P99: ~9.9s

    Returns:
        Number of events generated
    """
    print("\n📦 Setting up LATENCY scenario (100 events)...")
    # Generate uniform latencies from 1.0s to 10.0s
    latencies = [i / 10 for i in range(10, 101)]  # 1.0, 1.1, 1.2, ..., 10.0
    events = generator.generate_latency_test_dataset(
        latencies=latencies,
        status="delivered"
    )
    print(f"   ✅ Generated {len(events)} events with controlled latencies")
    print(f"   📊 Expected P50: ~5.5s, P95: ~9.5s, P99: ~9.9s")
    return len(events)


def setup_throughput_scenario(generator: TestDataGenerator) -> int:
    """
    Set up throughput test dataset for time-based metrics.

    Scenario: DO-4 (Throughput metrics over time)
    - 240 events distributed over 24 hours
    - 10 events per hour for consistent throughput

    Returns:
        Number of events generated
    """
    print("\n📦 Setting up THROUGHPUT scenario (240 events)...")
    events = generator.generate_throughput_dataset(
        events_per_hour=10,
        hours=24
    )
    print(f"   ✅ Generated {len(events)} events over 24 hours")
    print(f"   📊 Expected throughput: 10 events/hour")
    return len(events)


def setup_comprehensive_scenario(generator: TestDataGenerator) -> int:
    """
    Set up comprehensive dataset for all UAT scenarios.

    Combines multiple scenarios to support all 27 test scenarios:
    - Realistic dataset (200 events)
    - Failure scenario (50 events)
    - Various event types for filtering tests

    Returns:
        Total number of events generated
    """
    print("\n📦 Setting up COMPREHENSIVE scenario (multiple datasets)...")

    total_events = 0

    # Realistic baseline (200 events)
    print("   1/3: Generating realistic baseline (200 events)...")
    events = generator.generate_realistic_dataset(count=200, hours_ago_range=24)
    total_events += len(events)

    # High failure subset (50 events)
    print("   2/3: Generating high failure subset (50 events)...")
    events = generator.generate_high_failure_scenario(
        delivered=10,
        failed=35,
        pending=5
    )
    total_events += len(events)

    # Diverse event types for filtering (50 events)
    print("   3/3: Generating diverse event types (50 events)...")
    # Create 50 events with varied event types
    from datetime import datetime, timedelta
    import random

    event_types = [
        "order.created",
        "user.registered",
        "payment.processed",
        "invoice.generated",
        "shipment.dispatched"
    ]

    diverse_events = []
    for i in range(50):
        event_type = random.choice(event_types)
        status = random.choices(
            ["pending", "delivered", "failed"],
            weights=[10, 80, 10]
        )[0]

        created_at = (datetime.utcnow() - timedelta(hours=random.randint(1, 48))).isoformat() + "Z"

        event = {
            "event_type": event_type,
            "status": status,
            "created_at": created_at,
            "payload": {
                f"{event_type.split('.')[0]}_id": f"{event_type.upper()}-{i:04d}",
                "test_data": True
            }
        }

        diverse_events.append(event)

    generator.batch_insert(diverse_events)
    total_events += len(diverse_events)

    print(f"   ✅ Generated {total_events} total events (comprehensive scenario)")
    return total_events


def verify_data_loaded(table) -> Dict[str, Any]:
    """
    Verify that data was loaded successfully by counting events by status.

    Args:
        table: DynamoDB table resource

    Returns:
        Dictionary with event counts by status
    """
    print("\n🔍 Verifying data was loaded successfully...")

    # Scan table to count events
    response = table.scan()
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    # Count by status
    counts = {
        "total": len(items),
        "pending": 0,
        "delivered": 0,
        "failed": 0
    }

    for item in items:
        status = item.get("status", "unknown")
        if status in counts:
            counts[status] += 1

    print(f"   ✅ Total events: {counts['total']}")
    print(f"   📊 Pending: {counts['pending']}")
    print(f"   📊 Delivered: {counts['delivered']}")
    print(f"   📊 Failed: {counts['failed']}")

    if counts['total'] > 0:
        success_rate = (counts['delivered'] / (counts['delivered'] + counts['failed']) * 100) if (counts['delivered'] + counts['failed']) > 0 else 0
        print(f"   📊 Success Rate: {success_rate:.1f}%")

    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Set up sandbox environment for UAT testing"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before generating new data"
    )
    parser.add_argument(
        "--scenario",
        choices=["realistic", "failures", "latency", "throughput", "comprehensive", "all"],
        default="comprehensive",
        help="Scenario to set up (default: comprehensive)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("🚀 UAT Environment Setup - Sandbox")
    print("=" * 70)
    print(f"\n📍 Configuration:")
    print(f"   Region: {SANDBOX_CONFIG['region']}")
    print(f"   Table: {SANDBOX_CONFIG['table_name']}")
    print(f"   API URL: {SANDBOX_CONFIG['api_url']}")
    print(f"   Dashboard: {SANDBOX_CONFIG['dashboard_url']}")
    print(f"   Scenario: {args.scenario}")

    # Connect to DynamoDB
    try:
        dynamodb = boto3.resource("dynamodb", region_name=SANDBOX_CONFIG["region"])
        table = dynamodb.Table(SANDBOX_CONFIG["table_name"])
        generator = TestDataGenerator(table)
        print("\n✅ Connected to DynamoDB sandbox table")
    except Exception as e:
        print(f"\n❌ Failed to connect to DynamoDB: {e}")
        sys.exit(1)

    # Clear existing data if requested
    if args.clear:
        try:
            clear_table(table)
        except Exception as e:
            print(f"❌ Failed to clear table: {e}")
            sys.exit(1)

    # Generate test data based on scenario
    total_events = 0
    try:
        if args.scenario == "realistic":
            total_events = setup_realistic_scenario(generator)
        elif args.scenario == "failures":
            total_events = setup_failure_scenario(generator)
        elif args.scenario == "latency":
            total_events = setup_latency_scenario(generator)
        elif args.scenario == "throughput":
            total_events = setup_throughput_scenario(generator)
        elif args.scenario == "comprehensive":
            total_events = setup_comprehensive_scenario(generator)
        elif args.scenario == "all":
            # Run all scenarios
            total_events += setup_realistic_scenario(generator)
            total_events += setup_failure_scenario(generator)
            total_events += setup_latency_scenario(generator)
            total_events += setup_throughput_scenario(generator)
    except Exception as e:
        print(f"\n❌ Failed to generate test data: {e}")
        sys.exit(1)

    # Verify data was loaded
    try:
        counts = verify_data_loaded(table)

        if counts["total"] == 0:
            print("\n⚠️  Warning: No data found in table after generation!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Failed to verify data: {e}")
        sys.exit(1)

    # Success summary
    print("\n" + "=" * 70)
    print("✅ UAT Environment Setup Complete!")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"   Events generated: {total_events}")
    print(f"   Events in table: {counts['total']}")
    print(f"\n🌐 Access URLs:")
    print(f"   Dashboard: {SANDBOX_CONFIG['dashboard_url']}")
    print(f"   API: {SANDBOX_CONFIG['api_url']}")
    print(f"\n📝 Next Steps:")
    print(f"   1. Visit dashboard to verify data is visible")
    print(f"   2. Test API authentication with sandbox credentials")
    print(f"   3. Distribute access credentials to UAT participants")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
