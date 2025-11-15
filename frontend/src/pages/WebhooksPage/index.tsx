/**
 * Webhooks Page - Receiver UI for Webhook Deliveries (Task 25)
 *
 * Features:
 * - Real-time log of received webhooks with auto-refresh
 * - Filtering by event_type and date range
 * - Search functionality
 * - Test webhook sender tool with HMAC signature
 * - HMAC signature validator/generator utility
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Card } from '../../components/ui/card'
import { Webhook, RefreshCw, Pause, Play, Search, Filter, Send, ArrowLeft } from 'lucide-react'
import { WebhookLogTable } from '../../components/webhooks/WebhookLogTable'
import { WebhookTestSender } from '../../components/webhooks/WebhookTestSender'
import { HmacValidator } from '../../components/webhooks/HmacValidator'
import { useAuth } from '../../lib/useAuth'

const API_URL = import.meta.env.VITE_API_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'
const REFRESH_INTERVAL = 5000 // 5 seconds

export interface WebhookLog {
  id: string
  event_type: string
  payload: Record<string, any>
  source_ip: string
  timestamp: string
  status: string
  request_id?: string
}

export default function WebhooksPage() {
  const navigate = useNavigate()
  const { token, loading: authLoading, error: authError } = useAuth()
  const [logs, setLogs] = useState<WebhookLog[]>([])
  const [filteredLogs, setFilteredLogs] = useState<WebhookLog[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isPaused, setIsPaused] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Filter states
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  // Get unique event types for filter dropdown
  const uniqueEventTypes = Array.from(new Set(logs.map(log => log.event_type))).sort()

  // Fetch webhook logs
  const loadLogs = useCallback(async () => {
    if (!token) return

    try {
      setLoading(true)
      setError(null)

      // Build query params - /events/deliveries only supports limit parameter
      const params = new URLSearchParams()
      params.append('limit', '100')

      const response = await fetch(`${API_URL}/events/deliveries?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('Failed to fetch webhook deliveries')
      }

      const data = await response.json()

      // Apply client-side filtering since backend only supports limit
      let filtered = data
      if (eventTypeFilter && eventTypeFilter !== 'all') {
        filtered = filtered.filter((log: any) => log.type === eventTypeFilter)
      }
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        filtered = filtered.filter((log: any) =>
          log.id.toLowerCase().includes(query) ||
          log.type.toLowerCase().includes(query) ||
          JSON.stringify(log.payload).toLowerCase().includes(query)
        )
      }
      if (startDate) {
        const start = new Date(startDate).getTime()
        filtered = filtered.filter((log: any) => new Date(log.created_at).getTime() >= start)
      }
      if (endDate) {
        const end = new Date(endDate).getTime()
        filtered = filtered.filter((log: any) => new Date(log.created_at).getTime() <= end)
      }

      setLogs(data)
      setFilteredLogs(filtered)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load webhook logs')
    } finally {
      setLoading(false)
    }
  }, [token, eventTypeFilter, searchQuery, startDate, endDate])

  // Auto-refresh effect
  useEffect(() => {
    if (!token || isPaused) return

    loadLogs()

    const interval = setInterval(loadLogs, REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [token, isPaused, loadLogs])

  // Manual refresh handler
  const handleManualRefresh = () => {
    loadLogs()
  }

  // Toggle pause/resume
  const togglePause = () => {
    setIsPaused(!isPaused)
  }

  // Clear filters
  const handleClearFilters = () => {
    setEventTypeFilter('all')
    setSearchQuery('')
    setStartDate('')
    setEndDate('')
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
      <header className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
            <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-purple-600">
              <Webhook className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="font-mono text-3xl font-bold tracking-tight">
                Webhook Receiver
              </h1>
              <p className="text-sm text-muted-foreground">
                Real-time log of webhook deliveries
              </p>
            </div>
            <Badge variant="secondary" className="ml-2 font-mono text-xs">
              Live
            </Badge>
          </div>

          {/* Refresh Controls */}
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-xs text-muted-foreground mr-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleManualRefresh}
              disabled={loading || authLoading}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
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
        {!isPaused && (
          <p className="text-xs text-muted-foreground">
            Auto-refresh: {REFRESH_INTERVAL / 1000}s
          </p>
        )}
      </header>

      {/* Filters Section */}
      <section className="mb-6">
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Filters</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Event Type Filter */}
            <div className="space-y-2">
              <Label htmlFor="event-type-filter">Event Type</Label>
              <Select value={eventTypeFilter} onValueChange={setEventTypeFilter}>
                <SelectTrigger id="event-type-filter">
                  <SelectValue placeholder="All event types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All event types</SelectItem>
                  {uniqueEventTypes.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Search */}
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search in payload..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Date Range */}
            <div className="space-y-2">
              <Label htmlFor="start-date">Start Date</Label>
              <Input
                id="start-date"
                type="datetime-local"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="end-date">End Date</Label>
              <Input
                id="end-date"
                type="datetime-local"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Clear Filters Button */}
          {((eventTypeFilter && eventTypeFilter !== 'all') || searchQuery || startDate || endDate) && (
            <div className="mt-4 flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearFilters}
                className="gap-2"
              >
                Clear Filters
              </Button>
            </div>
          )}
        </Card>
      </section>

      {/* Webhook Log Table */}
      <section className="mb-8">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">
              Webhook Deliveries ({filteredLogs.length})
            </h2>
          </div>
          {error ? (
            <div className="p-6 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          ) : (
            <WebhookLogTable logs={filteredLogs} loading={loading || authLoading} />
          )}
        </Card>
      </section>

      {/* Test Tools Section */}
      <section className="grid md:grid-cols-2 gap-6 mb-8">
        {/* Webhook Test Sender */}
        <WebhookTestSender onWebhookSent={loadLogs} />

        {/* HMAC Validator */}
        <HmacValidator />
      </section>
    </div>
  )
}
