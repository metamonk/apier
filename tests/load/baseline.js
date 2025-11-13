/**
 * Baseline Load Test - 10 Concurrent Users
 *
 * This test establishes baseline performance metrics under normal load.
 * Tests all core API endpoints with JWT authentication.
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

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';
const API_KEY = __ENV.API_KEY;

if (!API_KEY) {
  throw new Error('API_KEY environment variable is required');
}

export const options = {
  vus: 10,
  duration: '2m',
  thresholds: {
    // Success rate: 99% of requests should succeed
    'http_req_failed': ['rate<0.01'],

    // Response times: Conservative baselines
    'http_req_duration': ['p(50)<500', 'p(95)<1000', 'p(99)<2000'],

    // Endpoint-specific thresholds
    'http_req_duration{endpoint:auth}': ['p(95)<800'],
    'http_req_duration{endpoint:events}': ['p(95)<1000'],
    'http_req_duration{endpoint:inbox}': ['p(95)<1200'],
    'http_req_duration{endpoint:ack}': ['p(95)<1000'],

    // Custom metrics
    'event_creation_duration': ['p(95)<1000'],
    'inbox_retrieval_duration': ['p(95)<1200'],
    'ack_duration': ['p(95)<1000'],
    'auth_failures': ['count<5'],

    // Overall success
    'checks': ['rate>0.95'],
  },
  tags: {
    test_type: 'baseline',
  },
};

// Authentication helper - cached token
let authToken = null;
let tokenExpiry = 0;

function getAuthToken() {
  const now = Date.now();

  // Return cached token if still valid (with 5 min buffer)
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

  // Detect cold starts (>1s response time typically indicates cold start)
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
  // Token expires in 24 hours, set expiry
  tokenExpiry = now + (23 * 60 * 60 * 1000);

  return authToken;
}

export default function () {
  // Get authentication token
  const token = getAuthToken();
  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  // 1. Create an event (POST /events)
  const eventPayload = JSON.stringify({
    type: 'user.action',
    source: 'load-test-baseline',
    payload: {
      user_id: `user-${__VU}-${__ITER}`,
      action: 'baseline_test',
      timestamp: new Date().toISOString(),
      iteration: __ITER,
      vu: __VU,
    },
  });

  const createStart = Date.now();
  const createResponse = http.post(
    `${BASE_URL}/events`,
    eventPayload,
    {
      headers,
      tags: { endpoint: 'events' },
    }
  );
  eventCreationDuration.add(Date.now() - createStart);

  const createSuccess = check(createResponse, {
    'create event: status is 201': (r) => r.status === 201,
    'create event: has event id': (r) => r.json('id') !== undefined,
    'create event: status is pending': (r) => r.json('status') === 'pending',
  });

  let eventId = null;
  if (createSuccess) {
    eventId = createResponse.json('id');
  }

  sleep(0.5);

  // 2. Retrieve inbox events (GET /inbox)
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
    'inbox: has events': (r) => r.json().length > 0,
  });

  sleep(0.5);

  // 3. Acknowledge an event (POST /inbox/{id}/ack)
  if (eventId) {
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
      'ack: has updated_at': (r) => r.json('updated_at') !== undefined,
    });
  }

  sleep(1);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'results/baseline-summary.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const enableColors = options.enableColors || false;

  const metrics = data.metrics;
  let output = '\n';
  output += `${indent}=== Baseline Load Test Summary ===\n\n`;
  output += `${indent}Test Duration: ${data.state.testRunDurationMs / 1000}s\n`;
  output += `${indent}Virtual Users: ${data.root_group.checks ? Object.keys(data.root_group.checks).length : 'N/A'}\n`;
  output += `${indent}Total Requests: ${metrics.http_reqs ? metrics.http_reqs.values.count : 0}\n\n`;

  output += `${indent}Response Times:\n`;
  output += `${indent}  p50: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(50)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  p95: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'].toFixed(2) : 'N/A'}ms\n`;
  output += `${indent}  p99: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(99)'].toFixed(2) : 'N/A'}ms\n\n`;

  output += `${indent}Error Rate: ${metrics.http_req_failed ? (metrics.http_req_failed.values.rate * 100).toFixed(2) : 'N/A'}%\n`;
  output += `${indent}Cold Start Rate: ${metrics.cold_start_rate ? (metrics.cold_start_rate.values.rate * 100).toFixed(2) : 'N/A'}%\n`;

  return output;
}
