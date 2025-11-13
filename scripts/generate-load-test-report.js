#!/usr/bin/env node

/**
 * Load Test Report Generator
 *
 * Aggregates k6 test results and generates a comprehensive performance report.
 */

const fs = require('fs');
const path = require('path');

const RESULTS_DIR = path.join(__dirname, '..', 'results');
const OUTPUT_FILE = path.join(RESULTS_DIR, 'load-test-report.md');

const TEST_FILES = [
  'baseline-summary.json',
  'moderate-summary.json',
  'high-load-summary.json',
  'spike-summary.json',
];

function loadTestResults(filename) {
  const filepath = path.join(RESULTS_DIR, filename);
  if (!fs.existsSync(filepath)) {
    return null;
  }

  try {
    const data = fs.readFileSync(filepath, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    console.error(`Error reading ${filename}: ${error.message}`);
    return null;
  }
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms.toFixed(2)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatRate(rate) {
  return `${(rate * 100).toFixed(2)}%`;
}

function getMetricValue(metrics, metricName, valueName = 'avg') {
  const metric = metrics[metricName];
  if (!metric || !metric.values) return 'N/A';

  const value = metric.values[valueName];
  if (value === undefined) return 'N/A';

  return value;
}

function generateTestSection(testName, data) {
  if (!data) {
    return `### ${testName}\n\n**Status:** No results available\n\n`;
  }

  const metrics = data.metrics;
  const state = data.state;

  let section = `### ${testName}\n\n`;
  section += `**Test Duration:** ${formatDuration(state.testRunDurationMs)}\n\n`;

  // Summary metrics
  const totalRequests = getMetricValue(metrics, 'http_reqs', 'count');
  const requestRate = getMetricValue(metrics, 'http_reqs', 'rate');
  const errorRate = getMetricValue(metrics, 'http_req_failed', 'rate');

  section += `**Throughput:**\n`;
  section += `- Total Requests: ${totalRequests}\n`;
  section += `- Requests/sec: ${typeof requestRate === 'number' ? requestRate.toFixed(2) : requestRate}\n`;
  section += `- Error Rate: ${typeof errorRate === 'number' ? formatRate(errorRate) : errorRate}\n\n`;

  // Response times
  const p50 = getMetricValue(metrics, 'http_req_duration', 'p(50)');
  const p95 = getMetricValue(metrics, 'http_req_duration', 'p(95)');
  const p99 = getMetricValue(metrics, 'http_req_duration', 'p(99)');
  const max = getMetricValue(metrics, 'http_req_duration', 'max');

  section += `**Response Times:**\n`;
  section += `- p50: ${typeof p50 === 'number' ? formatDuration(p50) : p50}\n`;
  section += `- p95: ${typeof p95 === 'number' ? formatDuration(p95) : p95}\n`;
  section += `- p99: ${typeof p99 === 'number' ? formatDuration(p99) : p99}\n`;
  section += `- max: ${typeof max === 'number' ? formatDuration(max) : max}\n\n`;

  // Custom metrics
  const coldStartRate = getMetricValue(metrics, 'cold_start_rate', 'rate');
  const dynamoThrottles = getMetricValue(metrics, 'dynamodb_throttles', 'count');
  const authFailures = getMetricValue(metrics, 'auth_failures', 'count');

  section += `**Custom Metrics:**\n`;
  section += `- Cold Start Rate: ${typeof coldStartRate === 'number' ? formatRate(coldStartRate) : coldStartRate}\n`;
  section += `- DynamoDB Throttles: ${dynamoThrottles}\n`;
  section += `- Auth Failures: ${authFailures}\n\n`;

  // Thresholds status
  if (data.thresholds) {
    section += `**Thresholds:**\n`;
    const passedCount = Object.values(data.thresholds).filter(t => t.ok).length;
    const totalCount = Object.keys(data.thresholds).length;
    section += `- Passed: ${passedCount}/${totalCount}\n`;

    const failed = Object.entries(data.thresholds)
      .filter(([_, t]) => !t.ok)
      .map(([name, _]) => name);

    if (failed.length > 0) {
      section += `- Failed: ${failed.join(', ')}\n`;
    }
    section += '\n';
  }

  return section;
}

function generateBottlenecksSection(allResults) {
  let section = `## Identified Bottlenecks\n\n`;

  const bottlenecks = [];

  // Analyze all test results for bottlenecks
  Object.entries(allResults).forEach(([testName, data]) => {
    if (!data || !data.metrics) return;

    const metrics = data.metrics;

    // Check error rate
    const errorRate = getMetricValue(metrics, 'http_req_failed', 'rate');
    if (typeof errorRate === 'number' && errorRate > 0.05) {
      bottlenecks.push({
        severity: 'HIGH',
        test: testName,
        issue: 'High Error Rate',
        detail: `${formatRate(errorRate)} error rate (threshold: 5%)`,
        recommendation: 'Investigate Lambda errors and DynamoDB throttling',
      });
    }

    // Check response time
    const p95 = getMetricValue(metrics, 'http_req_duration', 'p(95)');
    if (typeof p95 === 'number' && p95 > 2000) {
      bottlenecks.push({
        severity: 'MEDIUM',
        test: testName,
        issue: 'High Latency',
        detail: `p95 response time: ${formatDuration(p95)}`,
        recommendation: 'Consider increasing Lambda memory or enabling provisioned concurrency',
      });
    }

    // Check DynamoDB throttling
    const throttles = getMetricValue(metrics, 'dynamodb_throttles', 'count');
    if (typeof throttles === 'number' && throttles > 0) {
      bottlenecks.push({
        severity: 'HIGH',
        test: testName,
        issue: 'DynamoDB Throttling',
        detail: `${throttles} throttle events detected`,
        recommendation: 'Increase DynamoDB capacity or switch to provisioned mode',
      });
    }

    // Check cold starts
    const coldStartRate = getMetricValue(metrics, 'cold_start_rate', 'rate');
    if (typeof coldStartRate === 'number' && coldStartRate > 0.15) {
      bottlenecks.push({
        severity: 'MEDIUM',
        test: testName,
        issue: 'High Cold Start Rate',
        detail: `${formatRate(coldStartRate)} of requests hit cold starts`,
        recommendation: 'Enable provisioned concurrency or keep Lambda warm',
      });
    }

    // Check Lambda concurrency errors
    const concurrencyErrors = getMetricValue(metrics, 'lambda_concurrency_errors', 'count');
    if (typeof concurrencyErrors === 'number' && concurrencyErrors > 0) {
      bottlenecks.push({
        severity: 'CRITICAL',
        test: testName,
        issue: 'Lambda Concurrency Limits',
        detail: `${concurrencyErrors} concurrency limit errors`,
        recommendation: 'Increase Lambda reserved concurrency or request AWS quota increase',
      });
    }
  });

  if (bottlenecks.length === 0) {
    section += `✓ **No significant bottlenecks detected**\n\n`;
    section += `The system performed within acceptable thresholds across all test scenarios.\n\n`;
  } else {
    // Group by severity
    const critical = bottlenecks.filter(b => b.severity === 'CRITICAL');
    const high = bottlenecks.filter(b => b.severity === 'HIGH');
    const medium = bottlenecks.filter(b => b.severity === 'MEDIUM');

    [critical, high, medium].forEach(group => {
      if (group.length === 0) return;

      section += `### ${group[0].severity} Priority\n\n`;

      group.forEach(b => {
        section += `#### ${b.issue} (${b.test})\n\n`;
        section += `- **Detail:** ${b.detail}\n`;
        section += `- **Recommendation:** ${b.recommendation}\n\n`;
      });
    });
  }

  return section;
}

function generateRecommendationsSection() {
  return `## Optimization Recommendations

### Immediate Actions (Priority 1)

1. **Increase Lambda Memory**
   - Current: 512 MB
   - Recommended: 1024 MB
   - Expected Impact: 20-30% latency reduction
   - Cost Impact: ~2x Lambda costs (but better performance/$ ratio)

2. **Set Reserved Concurrency**
   - Current: Not set (shared account pool)
   - Recommended: 500 concurrent executions
   - Expected Impact: Prevents concurrency errors, guarantees capacity
   - Cost Impact: Minimal (just reservation)

3. **DynamoDB Capacity Planning**
   - Current: On-demand mode
   - Recommended: Enable auto-scaling or provisioned capacity
   - Expected Impact: Eliminates throttling
   - Cost Impact: More predictable, potentially lower for sustained traffic

### High Impact (Priority 2)

4. **Enable Provisioned Concurrency**
   - Recommended: 10-20 warm containers
   - Expected Impact: Eliminates cold starts for baseline load
   - Cost Impact: ~$50-100/month additional

5. **Implement Request Caching**
   - Target: GET /inbox endpoint
   - Cache TTL: 30 seconds
   - Expected Impact: 80% reduction in DynamoDB reads
   - Cost Impact: Minimal (CloudWatch costs)

6. **Add CloudFront Distribution**
   - Expected Impact: Lower latency, DDoS protection, SSL at edge
   - Cost Impact: ~$20-50/month

### Nice to Have (Priority 3)

7. **Optimize Lambda Package Size**
   - Remove unused dependencies
   - Use Lambda layers
   - Expected Impact: Faster cold starts

8. **Implement Connection Pooling**
   - Reuse DynamoDB connections
   - Expected Impact: 5-10% latency improvement

9. **Add Request Queuing (SQS)**
   - Decouple event ingestion
   - Expected Impact: Better burst handling, no lost events

10. **Use DynamoDB Streams**
    - For real-time event delivery
    - Expected Impact: Lower latency, no polling overhead

`;
}

function generateReport() {
  console.log('Generating load test report...');

  // Load all test results
  const allResults = {
    'Baseline (10 VUs)': loadTestResults('baseline-summary.json'),
    'Moderate Load (50 VUs)': loadTestResults('moderate-summary.json'),
    'High Load (100-150 VUs)': loadTestResults('high-load-summary.json'),
    'Spike Test (200 VUs)': loadTestResults('spike-summary.json'),
  };

  // Generate report
  let report = `# Load Testing Performance Report

**Generated:** ${new Date().toISOString()}

**API Endpoint:** https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws

---

## Executive Summary

This report summarizes the load testing results for the Zapier Triggers API across four test scenarios:
baseline (10 VUs), moderate load (50 VUs), high load (100-150 VUs), and spike test (200 VUs).

`;

  // Add test results sections
  report += `## Test Results\n\n`;

  Object.entries(allResults).forEach(([testName, data]) => {
    report += generateTestSection(testName, data);
  });

  // Add bottlenecks analysis
  report += generateBottlenecksSection(allResults);

  // Add recommendations
  report += generateRecommendationsSection();

  // Add infrastructure summary
  report += `## Current Infrastructure

**AWS Lambda:**
- Memory: 512 MB
- Timeout: 30 seconds
- Reserved Concurrency: Not set
- Provisioned Concurrency: Not configured

**DynamoDB:**
- Table: zapier-triggers-events
- Billing Mode: On-demand
- GSI: status-index

**Estimated Monthly Costs:**
- Lambda: $20-40 (varies with traffic)
- DynamoDB: $10-30 (on-demand)
- CloudWatch: $5-10
- Total: ~$35-80/month

## Next Steps

1. Review bottleneck analysis and prioritize fixes
2. Implement Priority 1 recommendations
3. Monitor CloudWatch metrics after changes
4. Re-run load tests to validate improvements
5. Set up continuous load testing in CI/CD pipeline

## Additional Resources

- [Load Testing Documentation](docs/LOAD_TESTING.md)
- [Monitoring Guide](docs/MONITORING.md)
- [Deployment Documentation](docs/DEPLOYMENT.md)

---

**Report Generated by:** generate-load-test-report.js
**Last Updated:** ${new Date().toISOString()}
`;

  // Write report
  fs.writeFileSync(OUTPUT_FILE, report);
  console.log(`Report generated: ${OUTPUT_FILE}`);

  // Also output to console
  console.log('\n' + report);

  return report;
}

// Main execution
if (require.main === module) {
  try {
    if (!fs.existsSync(RESULTS_DIR)) {
      console.error(`Error: Results directory not found: ${RESULTS_DIR}`);
      console.error('Run load tests first: npm run load-test:all');
      process.exit(1);
    }

    generateReport();
  } catch (error) {
    console.error('Error generating report:', error);
    process.exit(1);
  }
}

module.exports = { generateReport };
