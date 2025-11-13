/**
 * Spike Test - Sudden Traffic Surge
 *
 * This test simulates sudden traffic spikes to evaluate system
 * resilience and auto-scaling behavior.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const authFailures = new Counter('auth_failures');
const eventCreationDuration = new Trend('event_creation_duration');
const coldStartRate = new Rate('cold_start_rate');
const dynamodbThrottles = new Counter('dynamodb_throttles');
const timeoutErrors = new Counter('timeout_errors');
const lambdaConcurrencyErrors = new Counter('lambda_concurrency_errors');
const recoveryTime = new Trend('recovery_time');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';
const API_KEY = __ENV.API_KEY;

if (!API_KEY) {
  throw new Error('API_KEY environment variable is required');
}

export const options = {
  scenarios: {
    spike_test: {
      executor: 'ramping-vus',
      stages: [
        { duration: '30s', target: 10 },   // Normal load
        { duration: '10s', target: 200 },  // SPIKE! 20x increase
        { duration: '1m', target: 200 },   // Hold spike
        { duration: '30s', target: 10 },   // Back to normal
        { duration: '1m', target: 10 },    // Recovery observation
      ],
    },
  },
  thresholds: {
    // More lenient thresholds for spike test
    'http_req_failed': ['rate<0.10'],

    // Response times: Expect significant degradation during spike
    'http_req_duration': ['p(50)<2000', 'p(95)<5000', 'p(99)<10000'],

    // Custom metrics
    'event_creation_duration': ['p(95)<5000'],
    'auth_failures': ['count<100'],

    // Overall success - even more lenient for spike
    'checks': ['rate>0.75'],
  },
  tags: {
    test_type: 'spike',
  },
};

let authToken = null;
let tokenExpiry = 0;
let spikeStartTime = null;
let recoveryStartTime = null;

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
      timeout: '15s',
    }
  );

  const authDuration = Date.now() - authStart;

  if (authDuration > 1000) {
    coldStartRate.add(1);
  } else {
    coldStartRate.add(0);
  }

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
  // Detect spike phase
  const currentVUs = __ENV.K6_VUS || 0;
  if (currentVUs > 100 && !spikeStartTime) {
    spikeStartTime = Date.now();
    console.log('SPIKE DETECTED: Traffic surge initiated');
  }

  if (currentVUs < 50 && spikeStartTime && !recoveryStartTime) {
    recoveryStartTime = Date.now();
    const recoveryDuration = recoveryStartTime - spikeStartTime;
    recoveryTime.add(recoveryDuration);
    console.log(`RECOVERY DETECTED: System recovered in ${recoveryDuration}ms`);
  }

  const token = getAuthToken();
  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  // Simplified payload for spike test
  const payload = {
    type: 'spike.test',
    source: 'load-test-spike',
    payload: {
      user_id: `user-${__VU}-${__ITER}`,
      timestamp: new Date().toISOString(),
      vu: __VU,
      spike_phase: currentVUs > 100 ? 'active' : 'normal',
    },
  };

  // Focus on event creation during spike
  const createStart = Date.now();
  const createResponse = http.post(
    `${BASE_URL}/events`,
    JSON.stringify(payload),
    {
      headers,
      tags: { endpoint: 'events' },
      timeout: '15s',
    }
  );
  const createDuration = Date.now() - createStart;
  eventCreationDuration.add(createDuration);

  // Track errors
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

  check(createResponse, {
    'create event: not timeout': (r) => r.status !== 0 && r.status !== 504,
    'create event: success or retriable error': (r) =>
      r.status === 201 || r.status === 429 || r.status === 503,
  });

  // Minimal sleep - maximize load during spike
  sleep(0.05);
}

export function handleSummary(data) {
  const summary = generateSpikeSummary(data);

  return {
    'stdout': summary.text,
    'results/spike-summary.json': JSON.stringify({
      ...data,
      spike_analysis: summary.analysis,
    }, null, 2),
  };
}

function generateSpikeSummary(data) {
  const metrics = data.metrics;
  const indent = ' ';

  let text = '\n';
  text += `${indent}=== Spike Test Summary ===\n\n`;
  text += `${indent}Test Duration: ${data.state.testRunDurationMs / 1000}s\n`;
  text += `${indent}Total Requests: ${metrics.http_reqs ? metrics.http_reqs.values.count : 0}\n`;
  text += `${indent}Peak Requests/sec: ${metrics.http_reqs ? metrics.http_reqs.values.rate.toFixed(2) : 'N/A'}\n\n`;

  text += `${indent}Response Times During Spike:\n`;
  text += `${indent}  p50: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(50)'].toFixed(2) : 'N/A'}ms\n`;
  text += `${indent}  p95: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'].toFixed(2) : 'N/A'}ms\n`;
  text += `${indent}  p99: ${metrics.http_req_duration ? metrics.http_req_duration.values['p(99)'].toFixed(2) : 'N/A'}ms\n`;
  text += `${indent}  max: ${metrics.http_req_duration ? metrics.http_req_duration.values.max.toFixed(2) : 'N/A'}ms\n\n`;

  text += `${indent}Error Analysis:\n`;
  text += `${indent}  Error Rate: ${metrics.http_req_failed ? (metrics.http_req_failed.values.rate * 100).toFixed(2) : 'N/A'}%\n`;
  text += `${indent}  DynamoDB Throttles: ${metrics.dynamodb_throttles ? metrics.dynamodb_throttles.values.count : 0}\n`;
  text += `${indent}  Timeout Errors: ${metrics.timeout_errors ? metrics.timeout_errors.values.count : 0}\n`;
  text += `${indent}  Lambda Concurrency Errors: ${metrics.lambda_concurrency_errors ? metrics.lambda_concurrency_errors.values.count : 0}\n\n`;

  text += `${indent}System Behavior:\n`;
  text += `${indent}  Cold Start Rate: ${metrics.cold_start_rate ? (metrics.cold_start_rate.values.rate * 100).toFixed(2) : 'N/A'}%\n`;

  if (metrics.recovery_time && metrics.recovery_time.values.count > 0) {
    text += `${indent}  Recovery Time: ${(metrics.recovery_time.values.avg / 1000).toFixed(2)}s\n`;
  }

  // Analysis
  const analysis = {
    errorRate: metrics.http_req_failed ? metrics.http_req_failed.values.rate : 0,
    p95ResponseTime: metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'] : 0,
    throttleCount: metrics.dynamodb_throttles ? metrics.dynamodb_throttles.values.count : 0,
    concurrencyErrors: metrics.lambda_concurrency_errors ? metrics.lambda_concurrency_errors.values.count : 0,
    coldStartRate: metrics.cold_start_rate ? metrics.cold_start_rate.values.rate : 0,
  };

  text += `\n${indent}=== Spike Test Verdict ===\n`;

  if (analysis.errorRate < 0.05) {
    text += `${indent}✓ Excellent: System handled spike with <5% error rate\n`;
  } else if (analysis.errorRate < 0.10) {
    text += `${indent}⚠ Good: System handled spike with acceptable error rate\n`;
  } else {
    text += `${indent}✗ Poor: High error rate during spike - investigate capacity limits\n`;
  }

  if (analysis.throttleCount > 0) {
    text += `${indent}⚠ DynamoDB throttling detected - consider increasing capacity\n`;
  }

  if (analysis.concurrencyErrors > 0) {
    text += `${indent}⚠ Lambda concurrency limits hit - increase reserved concurrency\n`;
  }

  return { text, analysis };
}
