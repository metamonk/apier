/**
 * Metrics API Response Types
 * Matches the actual FastAPI backend responses from amplify/functions/api/main.py
 */

export interface EventSummary {
  total: number
  pending: number
  delivered: number
  failed: number
  success_rate: number
}

export interface LatencyMetrics {
  p50: number
  p95: number
  p99: number
  sample_size: number
}

export interface ThroughputMetrics {
  events_per_minute: number
  events_per_hour: number
  total_events_24h: number
  time_range: string
}

export interface ErrorMetrics {
  total_errors: number
  error_rate: number
  failed_deliveries: number
  pending_retries: number
}

export interface DashboardMetrics {
  summary: EventSummary
  latency: LatencyMetrics
  throughput: ThroughputMetrics
  errors: ErrorMetrics
  last_updated: string
}
