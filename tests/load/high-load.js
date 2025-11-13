/**
 * High Load Test - 100+ Concurrent Users
 *
 * This test pushes the system to high load levels to identify
 * performance bottlenecks and capacity limits.
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
const timeoutErrors = new Counter('timeout_errors');
const lambdaConcurrencyErrors = new Counter('lambda_concurrency_errors');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';
const API_KEY = __ENV.API_KEY;

if (!API_KEY) {
  throw new Error('API_KEY environment variable is required');
}

export const options = {
  scenarios: {
    high_load: {
      executor: 'ramping-vus',
      stages: [
        { duration: '1m', target: 20 },    // Warm up
        { duration: '2m', target: 50 },    // Ramp to moderate
        { duration: '2m', target: 100 },   // Ramp to high load
        { duration: '3m', target: 100 },   // Sustain high load
        { duration: '1m', target: 150 },   // Push further
        { duration: '2m', target: 150 },   // Hold peak
        { duration: '1m', target: 0 },     // Ramp down
      ],
    },
  },
  thresholds: {
    // Success rate: More lenient under high load
    'http_req_failed': ['rate<0.05'],

    // Response times: Expected degradation under high load
    'http_req_duration': ['p(50)<1000', 'p(95)<3000', 'p(99)<5000'],

    // Endpoint-specific thresholds
    'http_req_duration{endpoint:auth}': ['p(95)<2000'],
    'http_req_duration{endpoint:events}': ['p(95)<3000'],
    'http_req_duration{endpoint:inbox}': ['p(95)<3500'],
    'http_req_duration{endpoint:ack}': ['p(95)<2500'],

    // Custom metrics
    'event_creation_duration': ['p(95)<3000'],
    'inbox_retrieval_duration': ['p(95)<3500'],
    'ack_duration': ['p(95)<2500'],
    'auth_failures': ['count<50'],
    'dynamodb_throttles': ['count<100'],

    // Overall success - lower threshold for high load
    'checks': ['rate>0.85'],
  },
  tags: {
    test_type: 'high-load',
  },
};

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
      timeout: '10s',
    }
  );

  const authDuration = Date.now() - authStart;

  if (authDuration > 1000) {
    coldStartRate.add(1);
  } else {
    coldStartRate.add(0);
  }

  // Check for Lambda concurrency limits
  if (response.status === 429 || response.status === 503) {
    lambdaConcurrencyErrors.add(1);
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

  // Simulate realistic event types with varying payload sizes
  const eventTypes = [
    { type: 'user.created', size: 'small' },
    { type: 'order.placed', size: 'medium' },
    { type: 'payment.processed', size: 'medium' },
    { type: 'inventory.updated', size: 'large' },
  ];

  const selectedEvent = eventTypes[Math.floor(Math.random() * eventTypes.length)];

  // Generate payload based on size
  let payloadData = {
    user_id: `user-${__VU}-${__ITER}`,
    timestamp: new Date().toISOString(),
    vu: __VU,
    iteration: __ITER,
  };

  if (selectedEvent.size === 'medium') {
    payloadData.details = Array.from({ length: 10 }, (_, i) => ({
      field: `field_${i}`,
      value: `value_${Math.random().toString(36).substring(7)}`,
    }));
  } else if (selectedEvent.size === 'large') {
    payloadData.details = Array.from({ length: 20 }, (_, i) => ({
      field: `field_${i}`,
      value: `value_${Math.random().toString(36).substring(7)}`,
      metadata: {
        index: i,
        timestamp: Date.now(),
      },
    }));
  }

  const payload = {
    type: selectedEvent.type,
    source: 'load-test-high',
    payload: payloadData,
  };

  // 1. Create event with timeout handling
  const createStart = Date.now();
  const createResponse = http.post(
    `${BASE_URL}/events`,
    JSON.stringify(payload),
    {
      headers,
      tags: { endpoint: 'events' },
      timeout: '10s',
    }
  );
  eventCreationDuration.add(Date.now() - createStart);

  // Track specific error types
  if (createResponse.status === 503 || (createResponse.status === 500 &&
      createResponse.body && createResponse.body.includes('Throttling'))) {
    dynamodbThrottles.add(1);
  }

  if (createResponse.status === 0 || createResponse.status === 504) {
    timeoutErrors.add(1);
  }

  if (createResponse.status === 429 || createResponse.status === 503) {
    lambdaConcurrencyErrors.add(1);
  }

  const createSuccess = check(createResponse, {
    'create event: status is 201': (r) => r.status === 201,
    'create event: has event id': (r) => r.json('id') !== undefined,
    'create event: no timeout': (r) => r.status !== 0 && r.status !== 504,
  });

  let eventId = null;
  if (createSuccess) {
    eventId = createResponse.json('id');
  }

  // Shorter sleep under high load
  sleep(0.2);

  // 2. Retrieve inbox - less frequently under high load
  if (Math.random() < 0.5) { // 50% check inbox
    const inboxStart = Date.now();
    const inboxResponse = http.get(
      `${BASE_URL}/inbox`,
      {
        headers,
        tags: { endpoint: 'inbox' },
        timeout: '10s',
      }
    );
    inboxRetrievalDuration.add(Date.now() - inboxStart);

    check(inboxResponse, {
      'inbox: status is 200': (r) => r.status === 200,
      'inbox: returns array': (r) => Array.isArray(r.json()),
      'inbox: no timeout': (r) => r.status !== 0 && r.status !== 504,
    });

    sleep(0.2);
  }

  // 3. Acknowledge event
  if (eventId && Math.random() < 0.7) { // 70% ack rate
    const ackStart = Date.now();
    const ackResponse = http.post(
      `${BASE_URL}/inbox/${eventId}/ack`,
      null,
      {
        headers,
        tags: { endpoint: 'ack' },
        timeout: '10s',
      }
    );
    ackDuration.add(Date.now() - ackStart);

    check(ackResponse, {
      'ack: success or not found': (r) => r.status === 200 || r.status === 404,
      'ack: no timeout': (r) => r.status !== 0 && r.status !== 504,
    });
  }

  // Minimal sleep under high load
  sleep(Math.random() * 0.5 + 0.1);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'results/high-load-summary.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const metrics = data.metrics;

  let output = '\n';
  output += `${indent}=== High Load Test Summary ===\n\n`;
  output += `${indent}Test Duration: ${data.state.testRunDurationMs / 1000}s\n`;
  output += `${indent}Total Requests: ${metrics.http_reqs ? metrics.http_reqs.values.count : 0}\n`;
  output += `${indent}Requests/sec: ${metrics.http_reqs ? metrics.http_reqs.values.rate.toFixed(2) : 'N/A'}\n\n`;

  output += `${indent}Response Times:\n`;
  output += `${indent}  p50: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(50)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  p95: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  p99: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(99)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  max: ${metrics.http_req_duration ? metrics.http_req_duration.values.max.toFixed(2) : 'N/A'}ms\n\n`;

  output += `${indent}Errors:\n`;
  output += `${indent}  Error Rate: ${metrics.http_req_failed ? (metrics.http_req_failed.values.rate * 100).toFixed(2) : 'N/A'}%\n`;
  output += `${indent}  Auth Failures: ${metrics.auth_failures ? metrics.auth_failures.values.count : 0}\n`;
  output += `${indent}  DynamoDB Throttles: ${metrics.dynamodb_throttles ? metrics.dynamodb_throttles.values.count : 0}\n`;
  output += `${indent}  Timeout Errors: ${metrics.timeout_errors ? metrics.timeout_errors.values.count : 0}\n`;
  output += `${indent}  Lambda Concurrency Errors: ${metrics.lambda_concurrency_errors ? metrics.lambda_concurrency_errors.values.count : 0}\n\n`;

  output += `${indent}Performance:\n`;
  output += `${indent}  Cold Start Rate: ${metrics.cold_start_rate ? (metrics.cold_start_rate.values.rate * 100).toFixed(2) : 'N/A'}%\n`;

  return output;
}
