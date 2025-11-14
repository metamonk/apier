/**
 * Events Page - Events Management UI
 *
 * Features:
 * - Event list with search and filter (Task 26.1) ✅
 * - Event detail modal with JSON display (Task 26.2) ✅
 * - Export to CSV/JSON (Task 26.3) ✅
 * - Delete event action (Task 26.4) ✅
 * - Status indicators (Task 26.5) ✅
 * - Real-time updates with auto-refresh (Task 26.6) ✅
 */

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../lib/useAuth'
import { fetchEvents } from '../../lib/events-client'
import { EventFilters } from '../../components/events/EventFilters'
import { EventsTable } from '../../components/events/EventsTable'
import { EventDetailModal } from '../../components/events/EventDetailModal'
import { ExportButton } from '../../components/events/ExportButton'
import { Button } from '../../components/ui/button'
import { Badge } from '../../components/ui/badge'
import { Database, RefreshCw, Pause, Play, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { Event, EventFilters as EventFiltersType } from '../../lib/event-types'
import { useWebSocket } from '../../lib/useWebSocket'
import { ConnectionStatus } from '../../components/ConnectionStatus'

const REFRESH_INTERVAL = 15000 // 15 seconds

export default function EventsPage() {
  const navigate = useNavigate()
  const { token, loading: authLoading, error: authError } = useAuth()
  const [events, setEvents] = useState<Event[]>([])
  const [filteredEvents, setFilteredEvents] = useState<Event[]>([])
  const [filters, setFilters] = useState<EventFiltersType>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Load events
  const loadEvents = useCallback(async () => {
    if (!token) return

    try {
      setLoading(true)
      setError(null)
      const data = await fetchEvents(token)
      setEvents(data)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events')
      console.error('Load events error:', err)
    } finally {
      setLoading(false)
    }
  }, [token])

  // WebSocket connection for real-time event updates
  const ws = useWebSocket({
    enabled: !!token && !isPaused,
    onEventCreated: (event) => {
      // Add new event to the list
      setEvents((prev) => [event, ...prev])
      setLastUpdated(new Date())
    },
    onEventUpdate: (event) => {
      // Update existing event in the list
      setEvents((prev) =>
        prev.map((e) => (e.id === event.id ? { ...e, ...event } : e))
      )
      setLastUpdated(new Date())
    },
    onEventDeleted: (eventId) => {
      // Remove deleted event from the list
      setEvents((prev) => prev.filter((e) => e.id !== eventId))
      setLastUpdated(new Date())
    },
  })

  // Auto-refresh effect - only poll when WebSocket is not connected
  useEffect(() => {
    if (!token || isPaused || ws.isConnected) return

    loadEvents()

    const interval = setInterval(loadEvents, REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [token, isPaused, ws.isConnected, loadEvents])

  // Apply filters whenever events or filters change
  useEffect(() => {
    if (!events.length) {
      setFilteredEvents([])
      return
    }

    let result = [...events]

    // Apply filters
    if (filters.event_type) {
      result = result.filter((e) => e.type === filters.event_type)
    }
    if (filters.status) {
      result = result.filter((e) => e.status === filters.status)
    }
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      result = result.filter(
        (e) =>
          e.id.toLowerCase().includes(searchLower) ||
          e.type.toLowerCase().includes(searchLower) ||
          JSON.stringify(e.payload).toLowerCase().includes(searchLower)
      )
    }
    if (filters.start_date) {
      result = result.filter((e) => e.created_at >= filters.start_date!)
    }
    if (filters.end_date) {
      result = result.filter((e) => e.created_at <= filters.end_date!)
    }

    setFilteredEvents(result)
  }, [events, filters])

  // Get unique event types for filter dropdown
  const eventTypes = Array.from(new Set(events.map((e) => e.type))).sort()

  const handleEventClick = (event: Event) => {
    setSelectedEvent(event)
    setModalOpen(true)
  }

  const handleManualRefresh = () => {
    loadEvents()
  }

  const togglePause = () => {
    setIsPaused(!isPaused)
  }

  // Show auth error if authentication failed
  if (authError) {
    return (
      <div className="mx-auto min-h-screen w-full max-w-7xl p-6 md:p-8 lg:p-12">
        <div className="p-6 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
          <h3 className="font-semibold text-red-900 dark:text-red-100 mb-2">
            Authentication Error
          </h3>
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
            <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-primary">
              <Database className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="font-mono text-3xl font-bold tracking-tight">
                Events Management
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                {filteredEvents.length} of {events.length} events
              </p>
            </div>
            <Badge variant="secondary" className="ml-2 font-mono text-xs">
              Beta
            </Badge>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-xs text-muted-foreground mr-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <ConnectionStatus
              connectionState={ws.connectionState}
              onRetry={ws.reconnect}
              error={ws.error}
            />
            <ExportButton token={token || ''} filters={filters} disabled={!token} />
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
            {ws.isConnected
              ? 'Real-time updates active'
              : `Auto-refresh: ${REFRESH_INTERVAL / 1000}s`}
          </p>
        )}
      </header>

      {/* Filters */}
      <section className="mb-6">
        <EventFilters
          filters={filters}
          onFiltersChange={setFilters}
          eventTypes={eventTypes}
        />
      </section>

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {/* Events Table */}
      <section>
        <EventsTable
          events={filteredEvents}
          loading={authLoading || loading}
          onEventClick={handleEventClick}
          onEventsChange={loadEvents}
          token={token || ''}
        />
      </section>

      {/* Event Detail Modal */}
      <EventDetailModal
        event={selectedEvent}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  )
}
