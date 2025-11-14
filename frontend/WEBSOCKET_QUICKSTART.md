# WebSocket Integration - Quick Start Guide

**5-Minute Integration Guide for DashboardPage and EventsPage**

## Step 1: Add Environment Variable

Add to `frontend/.env`:
```bash
VITE_WEBSOCKET_URL=wss://your-api-gateway-url/production
```

Get this URL from AWS API Gateway WebSocket API or Amplify outputs after deployment.

## Step 2: Import Hook and Component

```typescript
import { useWebSocket, MessageType } from '../lib/useWebSocket'
import { ConnectionStatus } from '../components/ConnectionStatus'
import type { EventUpdate, MetricsUpdate } from '../lib/useWebSocket'
```

## Step 3: Add WebSocket Hook (DashboardPage Example)

```typescript
export default function DashboardPage() {
  const { token } = useAuth()
  const [summary, setSummary] = useState<EventSummary | null>(null)
  const [isPaused, setIsPaused] = useState(false)

  // Add WebSocket hook
  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: !isPaused && !!token,
    onMetricsUpdate: (metrics: MetricsUpdate) => {
      // Update summary with real-time data
      setSummary(prev => ({
        ...prev,
        total_events: metrics.total_events,
        pending_events: metrics.pending_events,
        delivered_events: metrics.delivered_events,
        failed_events: metrics.failed_events,
      }))
    },
  })

  // Existing code continues...
```

## Step 4: Update Polling Logic

Replace the existing auto-refresh effect:

```typescript
// BEFORE:
useEffect(() => {
  if (!token || isPaused) return
  loadMetrics()
  const interval = setInterval(loadMetrics, REFRESH_INTERVAL)
  return () => clearInterval(interval)
}, [token, isPaused, loadMetrics])

// AFTER:
useEffect(() => {
  if (!token || isPaused) return

  loadMetrics() // Initial load

  // Only use polling when WebSocket is NOT connected
  if (!ws.isConnected) {
    const interval = setInterval(loadMetrics, REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }
}, [token, isPaused, ws.isConnected, loadMetrics])
```

## Step 5: Add Connection Status to Header

```typescript
<header className="mb-12">
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-3">
      {/* Existing header content */}
    </div>

    {/* Add connection status */}
    <div className="flex items-center gap-2">
      <ConnectionStatus
        state={ws.state}
        reconnectAttempt={ws.reconnectAttempt}
        reconnectDelay={ws.reconnectDelay}
        onReconnect={ws.reconnect}
        showDetails={true}
      />

      {/* Existing controls (ThemeToggle, buttons, etc.) */}
    </div>
  </div>
</header>
```

## Step 6: EventsPage Integration

Similar pattern for EventsPage:

```typescript
export default function EventsPage() {
  const { token } = useAuth()
  const [events, setEvents] = useState<Event[]>([])
  const [isPaused, setIsPaused] = useState(false)

  const ws = useWebSocket({
    url: import.meta.env.VITE_WEBSOCKET_URL,
    token,
    enabled: !isPaused && !!token,

    // Handle new event created
    onEventCreated: (event: EventUpdate) => {
      setEvents(prev => [event as Event, ...prev])
    },

    // Handle event updated
    onEventUpdate: (event: EventUpdate) => {
      setEvents(prev =>
        prev.map(e => e.id === event.id ? { ...e, ...event } : e)
      )
    },

    // Handle event deleted
    onEventDeleted: (eventId: string) => {
      setEvents(prev => prev.filter(e => e.id !== eventId))
    },
  })

  // Update polling logic (same as DashboardPage)
  useEffect(() => {
    if (!token || isPaused) return
    loadEvents()
    if (!ws.isConnected) {
      const interval = setInterval(loadEvents, REFRESH_INTERVAL)
      return () => clearInterval(interval)
    }
  }, [token, isPaused, ws.isConnected, loadEvents])

  // Rest of component...
}
```

## That's It!

You now have:
- ✅ Real-time updates via WebSocket
- ✅ Automatic reconnection
- ✅ Fallback to polling when WebSocket unavailable
- ✅ Connection status display
- ✅ Zero breaking changes

## Testing

### 1. Check Connection
Open browser console and look for:
```
Connecting to WebSocket: wss://...
WebSocket connected
```

### 2. Verify Real-Time Updates
Create an event and watch it appear instantly without waiting for polling.

### 3. Test Reconnection
1. Disconnect network
2. See "Reconnecting..." status
3. Reconnect network
4. See automatic reconnection

### 4. Test Fallback
If WebSocket URL is not set, polling continues to work normally.

## Backend Requirements

The backend must implement a ping/pong handler. Add to your `$default` route Lambda:

```python
def handler(event, context):
    body = json.loads(event.get('body', '{}'))

    # Handle ping messages
    if body.get('type') == 'ping':
        return {
            'statusCode': 200,
            'body': json.dumps({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            })
        }

    # Handle other messages...
```

## Troubleshooting

### WebSocket Won't Connect
1. Check `VITE_WEBSOCKET_URL` is set in `.env`
2. Restart dev server after adding env var
3. Check browser console for errors

### Still Using Polling
1. Verify `ws.isConnected === true` in React DevTools
2. Check conditional in useEffect includes `ws.isConnected`
3. Ensure WebSocket URL is correct

### Connection Drops Frequently
1. Check backend is responding to ping messages
2. Verify network is stable
3. Check browser console for errors

## More Information

- **Full Documentation**: `WEBSOCKET_INTEGRATION.md`
- **Integration Examples**: `src/lib/useWebSocket.example.tsx`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`

## Support

If you encounter issues:
1. Check browser console for errors
2. Review `WEBSOCKET_INTEGRATION.md` troubleshooting section
3. Test with `wscat` to verify backend is working
4. Check that token is valid and not expired
