/**
 * WebSocket Hook - Integration Examples
 *
 * This file shows how to integrate the useWebSocket hook into pages.
 * DO NOT import this file - use it as a reference for integration.
 */

import { useWebSocket, MessageType } from './useWebSocket'
import { ConnectionStatus } from '../components/ConnectionStatus'
import type { EventUpdate, MetricsUpdate } from './useWebSocket'

/**
 * Example 1: Basic Integration in DashboardPage
 */
export function DashboardPageExample() {
  const { token } = useAuth()
  const [summary, setSummary] = useState<EventSummary | null>(null)
  const [isPaused, setIsPaused] = useState(false)

  // WebSocket connection with metrics updates
  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: !isPaused && !!token,
    onMetricsUpdate: (metrics: MetricsUpdate) => {
      // Update summary state with real-time metrics
      setSummary(prev => ({
        ...prev,
        total_events: metrics.total_events,
        pending_events: metrics.pending_events,
        delivered_events: metrics.delivered_events,
        failed_events: metrics.failed_events,
      }))
    },
    onOpen: () => {
      console.log('WebSocket connected - real-time updates enabled')
    },
    onError: (error) => {
      console.error('WebSocket error, falling back to polling', error)
    },
  })

  // Conditional polling fallback
  useEffect(() => {
    if (!token || isPaused) return

    // Only poll if WebSocket is not connected
    if (!ws.isConnected) {
      const interval = setInterval(() => {
        loadMetrics() // Existing polling function
      }, 10000)
      return () => clearInterval(interval)
    }
  }, [token, isPaused, ws.isConnected])

  return (
    <div>
      {/* Connection Status in Header */}
      <header>
        <ConnectionStatus
          state={ws.state}
          reconnectAttempt={ws.reconnectAttempt}
          reconnectDelay={ws.reconnectDelay}
          maxReconnectAttempts={10}
          lastError={ws.lastError}
          onReconnect={ws.reconnect}
          showDetails={true}
        />
      </header>

      {/* Rest of dashboard */}
      <EventCountCards summary={summary} loading={false} />
    </div>
  )
}

/**
 * Example 2: Events Page with Real-time Updates
 */
export function EventsPageExample() {
  const { token } = useAuth()
  const [events, setEvents] = useState<Event[]>([])
  const [isPaused, setIsPaused] = useState(false)

  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: !isPaused && !!token,
    onEventCreated: (event: EventUpdate) => {
      // Add new event to list
      setEvents(prev => [event as Event, ...prev])
    },
    onEventUpdate: (event: EventUpdate) => {
      // Update existing event
      setEvents(prev =>
        prev.map(e => e.id === event.id ? { ...e, ...event } : e)
      )
    },
    onEventDeleted: (eventId: string) => {
      // Remove deleted event
      setEvents(prev => prev.filter(e => e.id !== eventId))
    },
  })

  // Load initial events
  const loadEvents = useCallback(async () => {
    if (!token) return
    const data = await fetchEvents(token)
    setEvents(data)
  }, [token])

  // Initial load + polling fallback
  useEffect(() => {
    if (!token || isPaused) return

    loadEvents() // Initial load

    // Only poll if WebSocket not connected
    if (!ws.isConnected) {
      const interval = setInterval(loadEvents, 15000)
      return () => clearInterval(interval)
    }
  }, [token, isPaused, ws.isConnected, loadEvents])

  return (
    <div>
      <header>
        <ConnectionStatus
          state={ws.state}
          onReconnect={ws.reconnect}
        />
      </header>
      <EventsTable events={events} />
    </div>
  )
}

/**
 * Example 3: Optimistic Updates when Sending Events
 */
export function SendEventSheetExample() {
  const { token } = useAuth()
  const [events, setEvents] = useState<Event[]>([])

  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: !!token,
  })

  const handleSendEvent = async (eventData: any) => {
    // Generate temporary ID for optimistic update
    const tempId = `temp-${Date.now()}`
    const optimisticEvent: Event = {
      id: tempId,
      type: eventData.type,
      source: 'frontend',
      payload: eventData.payload,
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    // Optimistically add to list
    setEvents(prev => [optimisticEvent, ...prev])

    try {
      // Send to backend
      const response = await fetch(`${API_URL}/events`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(eventData),
      })

      const createdEvent = await response.json()

      // Replace optimistic event with real one
      setEvents(prev =>
        prev.map(e => e.id === tempId ? createdEvent : e)
      )
    } catch (error) {
      // Remove optimistic event on error
      setEvents(prev => prev.filter(e => e.id !== tempId))
      console.error('Failed to create event:', error)
    }
  }

  return (
    <button onClick={() => handleSendEvent({ type: 'test', payload: {} })}>
      Send Event
    </button>
  )
}

/**
 * Example 4: Custom Message Handling
 */
export function CustomMessageHandlingExample() {
  const { token } = useAuth()

  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: !!token,
    onMessage: (message) => {
      console.log('Received message:', message)

      // Handle custom message types
      if (message.type === MessageType.ERROR) {
        // Show error toast
        toast.error(message.error || 'WebSocket error')
      }
    },
  })

  // Send custom message
  const sendCustomMessage = () => {
    ws.send({
      type: MessageType.SUBSCRIBE,
      data: { channel: 'events' },
    })
  }

  return (
    <div>
      <button onClick={sendCustomMessage}>
        Subscribe to Events
      </button>
    </div>
  )
}

/**
 * Example 5: Manual Connection Control
 */
export function ManualControlExample() {
  const { token } = useAuth()

  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: false, // Don't auto-connect
  })

  return (
    <div>
      <ConnectionStatus
        state={ws.state}
        onReconnect={ws.reconnect}
      />

      <div className="flex gap-2">
        <button onClick={ws.connect}>
          Connect
        </button>
        <button onClick={ws.disconnect}>
          Disconnect
        </button>
        <button onClick={ws.reconnect}>
          Reconnect
        </button>
      </div>

      {ws.isConnected && (
        <div className="text-green-600">
          Connected to WebSocket
        </div>
      )}
    </div>
  )
}
