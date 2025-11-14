/**
 * Metrics Charts Component
 * Displays latency percentiles and throughput metrics with Recharts visualizations
 */

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { LatencyMetrics, ThroughputMetrics } from '../../lib/metrics-types'

interface MetricsChartsProps {
  latency: LatencyMetrics | null
  throughput: ThroughputMetrics | null
  loading?: boolean
}

export function MetricsCharts({ latency, throughput, loading }: MetricsChartsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="p-6 rounded-lg border border-border bg-card">
            <div className="h-64 bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>
    )
  }

  // Prepare latency data for bar chart
  const latencyData = latency
    ? [
        { name: 'P50 (Median)', value: latency.p50, fill: '#3b82f6' },
        { name: 'P95', value: latency.p95, fill: '#f59e0b' },
        { name: 'P99', value: latency.p99, fill: '#ef4444' },
      ]
    : []

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Latency Chart */}
      <div className="p-6 rounded-lg border border-border bg-card">
        <h3 className="text-lg font-semibold mb-4">Event Processing Latency</h3>
        {latency && latencyData.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={latencyData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" label={{ value: 'Seconds', position: 'insideBottom', offset: -5 }} />
                <YAxis type="category" dataKey="name" width={100} />
                <Tooltip formatter={(value: number) => `${value.toFixed(2)}s`} />
                <Bar dataKey="value" />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4 text-xs text-muted-foreground text-center">
              Based on {latency.sample_size.toLocaleString()} completed events
            </div>
          </>
        ) : (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            No latency data available
          </div>
        )}
      </div>

      {/* Throughput Metrics */}
      <div className="p-6 rounded-lg border border-border bg-card">
        <h3 className="text-lg font-semibold mb-4">Event Throughput (24h)</h3>
        {throughput ? (
          <div className="space-y-6">
            {/* Total Events */}
            <div className="text-center p-4 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
              <p className="text-sm font-medium text-blue-800 dark:text-blue-200 mb-1">
                Total Events
              </p>
              <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                {throughput.total_events_24h.toLocaleString()}
              </p>
              <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                Last 24 hours
              </p>
            </div>

            {/* Rates */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-muted">
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  Per Minute
                </p>
                <p className="text-2xl font-bold">
                  {throughput.events_per_minute.toFixed(2)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  avg events/min
                </p>
              </div>
              <div className="p-4 rounded-lg bg-muted">
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  Per Hour
                </p>
                <p className="text-2xl font-bold">
                  {throughput.events_per_hour.toFixed(2)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  avg events/hour
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            No throughput data available
          </div>
        )}
      </div>
    </div>
  )
}
