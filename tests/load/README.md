# Load Testing Quick Reference

## Prerequisites

Install k6:
```bash
# macOS
brew install k6

# Linux
sudo apt-get install k6

# Windows
winget install k6
```

Set API key:
```bash
export API_KEY="your-api-key-here"
```

## Quick Start

### Run Single Test

```bash
# Baseline (10 users, 2 min)
npm run load-test:baseline

# Moderate (50 users, 5 min)
npm run load-test:moderate

# High load (100-150 users, 12 min)
npm run load-test:high

# Spike test (200 users, 3.5 min)
npm run load-test:spike
```

### Run All Tests

```bash
npm run load-test:all
```

### Generate Report

```bash
npm run load-test:report
```

## Test Files

| File | Description | VUs | Duration | Success Criteria |
|------|-------------|-----|----------|------------------|
| `baseline.js` | Baseline performance | 10 | 2 min | Error rate <1%, p95 <1s |
| `moderate.js` | Moderate load | 50 | 5 min | Error rate <2%, p95 <1.5s |
| `high-load.js` | High load capacity | 100-150 | 12 min | Error rate <5%, p95 <3s |
| `spike.js` | Traffic surge resilience | 200 | 3.5 min | Error rate <10%, recovery |

## Custom Runs

### Override API Endpoint

```bash
k6 run --env API_KEY=$API_KEY --env BASE_URL=https://custom-api.com tests/load/baseline.js
```

### Save Results

```bash
k6 run --env API_KEY=$API_KEY tests/load/baseline.js --out json=results/custom-test.json
```

### Run with Different VU Count

```bash
k6 run --env API_KEY=$API_KEY --vus 20 --duration 5m tests/load/baseline.js
```

## Understanding Results

### Key Metrics

- **http_req_duration**: Response time (p50, p95, p99)
- **http_req_failed**: Error rate
- **http_reqs**: Total requests and RPS
- **cold_start_rate**: Percentage of cold Lambda starts
- **dynamodb_throttles**: DynamoDB throttling events

### Success Indicators

✓ Green checkmarks = Thresholds passed
✗ Red X marks = Thresholds failed

### Result Files

Results saved to:
- `results/baseline-summary.json`
- `results/moderate-summary.json`
- `results/high-load-summary.json`
- `results/spike-summary.json`
- `results/load-test-report.md` (generated report)

## Common Issues

### "API_KEY not set"

```bash
export API_KEY="your-api-key"
```

### "k6 command not found"

Install k6:
```bash
brew install k6  # macOS
```

### High error rates

Check:
1. API endpoint is correct
2. API key is valid
3. AWS resources are healthy
4. No DynamoDB throttling

### Slow responses

Check:
1. Lambda cold starts (see `cold_start_rate`)
2. DynamoDB performance
3. Network latency

## Next Steps

1. Review [Load Testing Documentation](../../docs/LOAD_TESTING.md)
2. Check [Performance Report](../../docs/PERFORMANCE_REPORT.md)
3. Monitor [CloudWatch Dashboard](../../docs/MONITORING.md)
4. Implement optimizations

## Tips

- Run tests during off-peak hours
- Allow 5-10 min between test runs for cooldown
- Monitor AWS costs during testing
- Check CloudWatch logs if errors occur
- Baseline test is good for CI/CD integration

## Support

Issues? Check:
- [Full Documentation](../../docs/LOAD_TESTING.md)
- [Monitoring Guide](../../docs/MONITORING.md)
- CloudWatch Logs
- GitHub Issues
