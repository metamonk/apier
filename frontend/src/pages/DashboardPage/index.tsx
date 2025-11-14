/**
 * Dashboard Page - Landing Page for API/er
 *
 * Real-time monitoring dashboard showing:
 * - Event count cards (Task 20.3) ✅
 * - Lifecycle flow visualization (Task 20.4) ✅
 * - Auto-refresh functionality (Task 20.6) ✅
 * - Latency & throughput charts (Task 20.5) ✅
 * - Send Event sheet (Task 20.7) ✅
 */

import { useState, useEffect, useCallback } from 'react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Zap, Pause, Play, RefreshCw, Database, Webhook } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { EventCountCards } from '../../components/dashboard/EventCountCards'
import { LifecycleFlow } from '../../components/dashboard/LifecycleFlow'
import { MetricsCharts } from '../../components/dashboard/MetricsCharts'
import { SendEventSheet } from '../../components/send-event/SendEventSheet'
import { useAuth } from '../../lib/useAuth'
import { fetchSummary, fetchLatency, fetchThroughput } from '../../lib/metrics-client'
import type { EventSummary, LatencyMetrics, ThroughputMetrics } from '../../lib/metrics-types'

const REFRESH_INTERVAL = 10000 // 10 seconds

export default function DashboardPage() {
  const navigate = useNavigate()
  const { token, loading: authLoading, error: authError } = useAuth()
  const [summary, setSummary] = useState<EventSummary | null>(null)
  const [latency, setLatency] = useState<LatencyMetrics | null>(null)
  const [throughput, setThroughput] = useState<ThroughputMetrics | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(false)
  const [metricsError, setMetricsError] = useState<string | null>(null)
  const [isPaused, setIsPaused] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Fetch all metrics data in parallel
  const loadMetrics = useCallback(async () => {
    if (!token) return

    try {
      setMetricsLoading(true)
      setMetricsError(null)

      // Fetch all metrics in parallel
      const [summaryData, latencyData, throughputData] = await Promise.all([
        fetchSummary(token),
        fetchLatency(token),
        fetchThroughput(token),
      ])

      setSummary(summaryData)
      setLatency(latencyData)
      setThroughput(throughputData)
      setLastUpdated(new Date())
    } catch (err) {
      setMetricsError(err instanceof Error ? err.message : 'Failed to load metrics')
    } finally {
      setMetricsLoading(false)
    }
  }, [token])

  // Auto-refresh effect
  useEffect(() => {
    if (!token || isPaused) return

    loadMetrics()

    const interval = setInterval(loadMetrics, REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [token, isPaused, loadMetrics])

  // Manual refresh handler
  const handleManualRefresh = () => {
    loadMetrics()
  }

  // Toggle pause/resume
  const togglePause = () => {
    setIsPaused(!isPaused)
  }

  // Show auth error if authentication failed
  if (authError) {
    return (
      <div className="mx-auto min-h-screen w-full max-w-7xl p-6 md:p-8 lg:p-12">
        <div className="p-6 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
          <h3 className="font-semibold text-red-900 dark:text-red-100 mb-2">Authentication Error</h3>
          <p className="text-sm text-red-800 dark:text-red-200">{authError}</p>
          <p className="text-xs text-red-700 dark:text-red-300 mt-2">
            Please check your VITE_API_KEY environment variable.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto min-h-screen w-full max-w-7xl p-6 md:p-8 lg:p-12">
      {/* Header */}
      <header className="mb-12">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-primary">
              <Zap className="h-5 w-5 text-primary-foreground" />
            </div>
            <h1 className="font-mono text-3xl font-bold tracking-tight">
              api<span className="text-primary">/</span>er
            </h1>
            <Badge variant="secondary" className="ml-2 font-mono text-xs">
              Beta
            </Badge>
          </div>

          {/* Refresh Controls */}
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-xs text-muted-foreground mr-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <SendEventSheet onEventSent={loadMetrics} />
            <Button
              variant="outline"
              size="sm"
              onClick={handleManualRefresh}
              disabled={metricsLoading || authLoading}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${metricsLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={togglePause}
              className="gap-2"
            >
              {isPaused ? (
                <>
                  <Play className="h-4 w-4" />
                  Resume
                </>
              ) : (
                <>
                  <Pause className="h-4 w-4" />
                  Pause
                </>
              )}
            </Button>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <p className="text-muted-foreground">
            Real-time monitoring dashboard for API events
          </p>
          {!isPaused && (
            <p className="text-xs text-muted-foreground">
              Auto-refresh: {REFRESH_INTERVAL / 1000}s
            </p>
          )}
        </div>
      </header>

      {/* Quick Navigation */}
      <section className="mb-8">
        <div className="grid gap-4 sm:grid-cols-2">
          <Button
            variant="outline"
            className="h-auto p-6 justify-start gap-4 hover:bg-primary/10 hover:border-primary/50 transition-colors"
            onClick={() => navigate('/events')}
          >
            <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-primary/10">
              <Database className="h-6 w-6 text-primary" />
            </div>
            <div className="text-left">
              <div className="font-semibold mb-1">Events Management</div>
              <div className="text-sm text-muted-foreground">
                View, filter, and export all events
              </div>
            </div>
          </Button>
          <Button
            variant="outline"
            className="h-auto p-6 justify-start gap-4 hover:bg-primary/10 hover:border-primary/50 transition-colors"
            onClick={() => navigate('/webhooks')}
          >
            <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-primary/10">
              <Webhook className="h-6 w-6 text-primary" />
            </div>
            <div className="text-left">
              <div className="font-semibold mb-1">Webhook Receiver</div>
              <div className="text-sm text-muted-foreground">
                Monitor incoming webhook events
              </div>
            </div>
          </Button>
        </div>
      </section>

      {/* Event Count Cards */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Event Summary</h2>
        {metricsError ? (
          <div className="p-6 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
            <p className="text-sm text-red-800 dark:text-red-200">{metricsError}</p>
          </div>
        ) : (
          <EventCountCards summary={summary} loading={authLoading || metricsLoading} />
        )}
      </section>

      {/* Lifecycle Flow Visualization */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Event Lifecycle</h2>
        {metricsError ? (
          <div className="p-6 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
            <p className="text-sm text-red-800 dark:text-red-200">{metricsError}</p>
          </div>
        ) : (
          <div className="p-6 rounded-lg border border-border bg-card">
            <LifecycleFlow summary={summary} loading={authLoading || metricsLoading} />
          </div>
        )}
      </section>

      {/* Latency & Throughput Charts */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Performance Metrics</h2>
        {metricsError ? (
          <div className="p-6 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
            <p className="text-sm text-red-800 dark:text-red-200">{metricsError}</p>
          </div>
        ) : (
          <MetricsCharts
            latency={latency}
            throughput={throughput}
            loading={authLoading || metricsLoading}
          />
        )}
      </section>
    </div>
  )
}
