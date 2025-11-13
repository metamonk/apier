/**
 * Moderate Load Test - 50 Concurrent Users
 *
 * This test evaluates system performance under moderate load conditions,
 * simulating typical production usage patterns.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const authFailures = new Counter('auth_failures');
const eventCreationDuration = new Trend('event_creation_duration');
const inboxRetrievalDuration = new Trend('inbox_retrieval_duration');
const ackDuration = new Trend('ack_duration');
const coldStartRate = new Rate('cold_start_rate');
const dynamodbThrottles = new Counter('dynamodb_throttles');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';
const API_KEY = __ENV.API_KEY;

if (!API_KEY) {
  throw new Error('API_KEY environment variable is required');
}

export const options = {
  scenarios: {
    moderate_load: {
      executor: 'ramping-vus',
      stages: [
        { duration: '30s', target: 10 },  // Warm up
        { duration: '1m', target: 50 },   // Ramp to moderate load
        { duration: '3m', target: 50 },   // Sustain load
        { duration: '30s', target: 0 },   // Ramp down
      ],
    },
  },
  thresholds: {
    // Success rate: 98% should succeed under moderate load
    'http_req_failed': ['rate<0.02'],

    // Response times: Slightly more lenient for moderate load
    'http_req_duration': ['p(50)<600', 'p(95)<1500', 'p(99)<3000'],

    // Endpoint-specific thresholds
    'http_req_duration{endpoint:auth}': ['p(95)<1000'],
    'http_req_duration{endpoint:events}': ['p(95)<1500'],
    'http_req_duration{endpoint:inbox}': ['p(95)<2000'],
    'http_req_duration{endpoint:ack}': ['p(95)<1500'],

    // Custom metrics
    'event_creation_duration': ['p(95)<1500'],
    'inbox_retrieval_duration': ['p(95)<2000'],
    'ack_duration': ['p(95)<1500'],
    'auth_failures': ['count<10'],
    'dynamodb_throttles': ['count<5'],

    // Overall success
    'checks': ['rate>0.93'],
  },
  tags: {
    test_type: 'moderate',
  },
};

// Token cache per VU
let authToken = null;
let tokenExpiry = 0;

function getAuthToken() {
  const now = Date.now();

  if (authToken && tokenExpiry > now + 300000) {
    return authToken;
  }

  const authStart = Date.now();
  const response = http.post(
    `${BASE_URL}/token`,
    {
      username: 'api',
      password: API_KEY,
    },
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      tags: { endpoint: 'auth' },
    }
  );

  const authDuration = Date.now() - authStart;

  if (authDuration > 1000) {
    coldStartRate.add(1);
  } else {
    coldStartRate.add(0);
  }

  const authSuccess = check(response, {
    'auth: status is 200': (r) => r.status === 200,
    'auth: has access token': (r) => r.json('access_token') !== undefined,
  });

  if (!authSuccess) {
    authFailures.add(1);
    console.error(`Auth failed: ${response.status} - ${response.body}`);
    return null;
  }

  const data = response.json();
  authToken = data.access_token;
  tokenExpiry = now + (23 * 60 * 60 * 1000);

  return authToken;
}

export default function () {
  const token = getAuthToken();
  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  // Realistic payload sizes
  const payload = {
    type: ['user.created', 'user.updated', 'order.placed', 'payment.processed'][Math.floor(Math.random() * 4)],
    source: 'load-test-moderate',
    payload: {
      user_id: `user-${__VU}-${__ITER}`,
      session_id: `session-${Date.now()}-${Math.random()}`,
      action: 'moderate_load_test',
      timestamp: new Date().toISOString(),
      metadata: {
        iteration: __ITER,
        vu: __VU,
        test_phase: 'moderate',
      },
      // Add some variable data to test payload handling
      data: Array.from({ length: Math.floor(Math.random() * 5) + 1 }, (_, i) => ({
        key: `field_${i}`,
        value: `value_${Math.random()}`,
      })),
    },
  };

  // 1. Create event
  const createStart = Date.now();
  const createResponse = http.post(
    `${BASE_URL}/events`,
    JSON.stringify(payload),
    {
      headers,
      tags: { endpoint: 'events' },
    }
  );
  eventCreationDuration.add(Date.now() - createStart);

  // Check for DynamoDB throttling
  if (createResponse.status === 503 || (createResponse.status === 500 &&
      createResponse.body.includes('Throttling'))) {
    dynamodbThrottles.add(1);
  }

  const createSuccess = check(createResponse, {
    'create event: status is 201': (r) => r.status === 201,
    'create event: has event id': (r) => r.json('id') !== undefined,
  });

  let eventId = null;
  if (createSuccess) {
    eventId = createResponse.json('id');
  }

  sleep(0.3);

  // 2. Retrieve inbox (with varying frequency)
  if (Math.random() < 0.7) { // 70% of iterations check inbox
    const inboxStart = Date.now();
    const inboxResponse = http.get(
      `${BASE_URL}/inbox`,
      {
        headers,
        tags: { endpoint: 'inbox' },
      }
    );
    inboxRetrievalDuration.add(Date.now() - inboxStart);

    check(inboxResponse, {
      'inbox: status is 200': (r) => r.status === 200,
      'inbox: returns array': (r) => Array.isArray(r.json()),
    });

    sleep(0.3);
  }

  // 3. Acknowledge event
  if (eventId && Math.random() < 0.8) { // 80% ack rate
    const ackStart = Date.now();
    const ackResponse = http.post(
      `${BASE_URL}/inbox/${eventId}/ack`,
      null,
      {
        headers,
        tags: { endpoint: 'ack' },
      }
    );
    ackDuration.add(Date.now() - ackStart);

    check(ackResponse, {
      'ack: status is 200': (r) => r.status === 200,
      'ack: status is delivered': (r) => r.json('status') === 'delivered',
    });
  }

  // Variable think time
  sleep(Math.random() * 2 + 0.5);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'results/moderate-summary.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const metrics = data.metrics;

  let output = '\n';
  output += `${indent}=== Moderate Load Test Summary ===\n\n`;
  output += `${indent}Test Duration: ${data.state.testRunDurationMs / 1000}s\n`;
  output += `${indent}Total Requests: ${metrics.http_reqs ? metrics.http_reqs.values.count : 0}\n`;
  output += `${indent}Requests/sec: ${metrics.http_reqs ? metrics.http_reqs.values.rate.toFixed(2) : 'N/A'}\n\n`;

  output += `${indent}Response Times:\n`;
  output += `${indent}  p50: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(50)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  p95: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  p99: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(99)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  max: ${metrics.http_req_duration ? metrics.http_req_duration.values.max.toFixed(2) : 'N/A'}ms\n\n`;

  output += `${indent}Error Rate: ${metrics.http_req_failed ? (metrics.http_req_failed.values.rate * 100).toFixed(2) : 'N/A'}%\n`;
  output += `${indent}Cold Start Rate: ${metrics.cold_start_rate ? (metrics.cold_start_rate.values.rate * 100).toFixed(2) : 'N/A'}%\n`;
  output += `${indent}DynamoDB Throttles: ${metrics.dynamodb_throttles ? metrics.dynamodb_throttles.values.count : 0}\n`;

  return output;
}
