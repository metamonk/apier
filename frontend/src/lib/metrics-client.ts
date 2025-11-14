/**
 * Metrics API Client
 * Fetches metrics data from the backend API endpoints
 *
 * NOTE: This client accepts a JWT token as a parameter - it does NOT manage auth.
 * Token management is handled by the parent App component's auth flow.
 */

import type {
  EventSummary,
  LatencyMetrics,
  ThroughputMetrics,
  ErrorMetrics,
  DashboardMetrics,
} from './metrics-types'

const API_URL = import.meta.env.VITE_API_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

interface FetchOptions {
  token: string
}

async function fetchWithAuth(endpoint: string, options: FetchOptions): Promise<any> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      'Authorization': `Bearer ${options.token}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

export async function fetchSummary(token: string): Promise<EventSummary> {
  return fetchWithAuth('/metrics/summary', { token })
}

export async function fetchLatency(token: string): Promise<LatencyMetrics> {
  return fetchWithAuth('/metrics/latency', { token })
}

export async function fetchThroughput(token: string): Promise<ThroughputMetrics> {
  return fetchWithAuth('/metrics/throughput', { token })
}

export async function fetchErrors(token: string): Promise<ErrorMetrics> {
  return fetchWithAuth('/metrics/errors', { token })
}

export async function fetchAllMetrics(token: string): Promise<DashboardMetrics> {
  const [summary, latency, throughput, errors] = await Promise.all([
    fetchSummary(token),
    fetchLatency(token),
    fetchThroughput(token),
    fetchErrors(token),
  ])

  return {
    summary,
    latency,
    throughput,
    errors,
    last_updated: new Date().toISOString(),
  }
}
