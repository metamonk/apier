# WebSocket Integration Guide

This document explains the WebSocket infrastructure for real-time event updates in the API/er frontend.

## Overview

The WebSocket implementation provides:
- Real-time event updates without polling
- Automatic reconnection with exponential backoff
- Heartbeat/ping-pong for connection health
- Graceful fallback to polling when WebSocket unavailable
- Browser tab visibility handling
- Type-safe message handling

## Files Created

### Core Hook
**`frontend/src/lib/useWebSocket.ts`**
- React hook for WebSocket connection management
- Connection state tracking
- Message type definitions and handlers
- Reconnection logic with exponential backoff
- Heartbeat mechanism
- Tab visibility handling

### UI Component
**`frontend/src/components/ConnectionStatus.tsx`**
- Visual connection status indicator
- Reconnection countdown display
- Manual retry button
- Error message display
- Color-coded states (green/yellow/red/gray)

### Examples
**`frontend/src/lib/useWebSocket.example.tsx`**
- Integration patterns for DashboardPage
- Integration patterns for EventsPage
- Optimistic update patterns
- Custom message handling examples
- Manual connection control

## Message Types

```typescript
enum MessageType {
  PING = 'ping',                  // Heartbeat request
  PONG = 'pong',                  // Heartbeat response
  EVENT_UPDATE = 'event_update',  // Event status changed
  EVENT_CREATED = 'event_created', // New event created
  EVENT_DELETED = 'event_deleted', // Event deleted
  METRICS_UPDATE = 'metrics_update', // Dashboard metrics update
  SUBSCRIBE = 'subscribe',        // Subscribe to channel
  UNSUBSCRIBE = 'unsubscribe',    // Unsubscribe from channel
  ERROR = 'error',                // Error message
}
```

## Message Format

All WebSocket messages follow this structure:

```typescript
interface WebSocketMessage {
  type: MessageType
  data?: any
  timestamp?: string
  error?: string
}
```

### Event Update Message
```json
{
  "type": "event_update",
  "data": {
    "id": "evt_123",
    "status": "delivered",
    "delivery_latency_ms": 150,
    "updated_at": "2025-11-14T17:30:00Z"
  },
  "timestamp": "2025-11-14T17:30:00Z"
}
```

### Metrics Update Message
```json
{
  "type": "metrics_update",
  "data": {
    "total_events": 1250,
    "pending_events": 5,
    "delivered_events": 1200,
    "failed_events": 45
  },
  "timestamp": "2025-11-14T17:30:00Z"
}
```

## Connection States

```typescript
enum WebSocketState {
  CONNECTING = 'connecting',      // Initial connection attempt
  CONNECTED = 'connected',        // Successfully connected
  DISCONNECTED = 'disconnected',  // Not connected
  ERROR = 'error',                // Connection error
  RECONNECTING = 'reconnecting',  // Attempting to reconnect
}
```

## Configuration

### Environment Variables

Add to `frontend/.env`:

```env
VITE_WEBSOCKET_URL=wss://your-websocket-url.amazonaws.com/production
```

### Hook Configuration

```typescript
interface UseWebSocketConfig {
  url?: string                    // WebSocket URL (default: VITE_WEBSOCKET_URL)
  token?: string                  // JWT token for authentication
  enabled?: boolean               // Enable/disable connection (default: true)
  reconnect?: boolean             // Enable auto-reconnect (default: true)
  maxReconnectAttempts?: number   // Max retry attempts (default: 10)
  initialReconnectDelay?: number  // Initial backoff delay (default: 1000ms)
  maxReconnectDelay?: number      // Max backoff delay (default: 30000ms)
  heartbeatInterval?: number      // Ping interval (default: 30000ms)
  heartbeatTimeout?: number       // Pong timeout (default: 5000ms)

  // Event handlers
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onMessage?: (message: WebSocketMessage) => void
  onEventUpdate?: (event: EventUpdate) => void
  onEventCreated?: (event: EventUpdate) => void
  onEventDeleted?: (eventId: string) => void
  onMetricsUpdate?: (metrics: MetricsUpdate) => void
}
```

## Integration Steps

### Step 1: Import Hook and Component

```typescript
import { useWebSocket } from '../lib/useWebSocket'
import { ConnectionStatus } from '../components/ConnectionStatus'
import type { EventUpdate, MetricsUpdate } from '../lib/useWebSocket'
```

### Step 2: Add WebSocket Hook to Page

```typescript
const { token } = useAuth()
const [summary, setSummary] = useState<EventSummary | null>(null)

const ws = useWebSocket({
  url: import.meta.env.VITE_WEBSOCKET_URL,
  token,
  enabled: !!token,
  onMetricsUpdate: (metrics: MetricsUpdate) => {
    setSummary(prev => ({
      ...prev,
      ...metrics,
    }))
  },
})
```

### Step 3: Add Connection Status to UI

```tsx
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
```

### Step 4: Implement Polling Fallback

```typescript
useEffect(() => {
  if (!token || isPaused) return

  // Only use polling when WebSocket is not connected
  if (!ws.isConnected) {
    const interval = setInterval(() => {
      loadMetrics() // Existing polling function
    }, 10000)
    return () => clearInterval(interval)
  }
}, [token, isPaused, ws.isConnected])
```

## Reconnection Logic

### Exponential Backoff

The hook implements exponential backoff with jitter:

```typescript
delay = min(maxDelay, initialDelay * 2^attempt) + random(0-1000)
```

Example sequence:
1. Attempt 1: ~1s
2. Attempt 2: ~2s
3. Attempt 3: ~4s
4. Attempt 4: ~8s
5. Attempt 5: ~16s
6. Attempt 6+: ~30s (max)

After 10 failed attempts, reconnection stops.

### Heartbeat Mechanism

- Sends PING every 30 seconds
- Expects PONG within 5 seconds
- Closes connection if PONG not received
- Automatic reconnection triggered

### Tab Visibility

- Stops heartbeat when tab hidden (saves resources)
- Resumes when tab becomes visible
- Reconnects if connection lost while hidden

## Backend Requirements

The WebSocket API Gateway must support:

### 1. Authentication
Accept token as query parameter:
```
wss://your-url.amazonaws.com/production?token=<jwt-token>
```

### 2. Ping/Pong Handler
Respond to ping messages:
```python
if message.get('type') == 'ping':
    return {
        'type': 'pong',
        'timestamp': datetime.now().isoformat()
    }
```

### 3. Message Broadcasting
Send updates to connected clients:
```python
# Event update
{
    'type': 'event_update',
    'data': {
        'id': event_id,
        'status': new_status,
        'updated_at': timestamp
    }
}

# Metrics update
{
    'type': 'metrics_update',
    'data': {
        'total_events': count,
        'pending_events': pending,
        'delivered_events': delivered,
        'failed_events': failed
    }
}
```

## Testing

### Manual Testing

```bash
# Install wscat for testing
npm install -g wscat

# Connect to WebSocket
wscat -c "wss://your-url.amazonaws.com/production?token=YOUR_TOKEN"

# Send ping
> {"type": "ping", "timestamp": "2025-11-14T17:30:00Z"}

# Should receive pong
< {"type": "pong", "timestamp": "2025-11-14T17:30:00Z"}
```

### Test Scenarios

1. **Normal Operation**
   - WebSocket connects successfully
   - Receives real-time updates
   - Polling disabled

2. **Connection Lost**
   - Network interruption
   - Shows "Reconnecting..." with countdown
   - Automatically reconnects
   - Falls back to polling during reconnection

3. **Max Retries Exceeded**
   - After 10 failed attempts
   - Shows "Disconnected" with retry button
   - Falls back to polling
   - Manual retry available

4. **Tab Visibility**
   - Hide tab → heartbeat stops
   - Show tab → heartbeat resumes
   - Reconnects if needed

5. **No WebSocket URL**
   - Hook disabled
   - Uses polling only
   - No errors thrown

## Browser Compatibility

Supported browsers:
- Chrome 88+
- Firefox 85+
- Safari 14+
- Edge 88+

All modern browsers support WebSocket API natively.

## Performance Considerations

### Memory Usage
- Single WebSocket connection per page
- Minimal overhead (~1-2KB per message)
- Heartbeat messages every 30s

### Network Usage
- No polling when connected (saves bandwidth)
- ~100 bytes per heartbeat (every 30s)
- Event messages: ~500-2000 bytes each

### CPU Usage
- Minimal impact
- Event-driven architecture
- No polling timers when connected

## Troubleshooting

### WebSocket Won't Connect

1. Check environment variable:
   ```bash
   echo $VITE_WEBSOCKET_URL
   ```

2. Verify token is valid:
   ```typescript
   console.log('Token:', token)
   ```

3. Check browser console for errors

4. Test with wscat (see Testing section)

### Connection Keeps Dropping

1. Check heartbeat configuration
2. Verify backend sends pong responses
3. Check network stability
4. Review browser dev tools Network tab

### Messages Not Received

1. Verify message format matches interface
2. Check onMessage handler is defined
3. Enable debug logging:
   ```typescript
   onMessage: (msg) => console.log('WS message:', msg)
   ```

### Polling Still Active

1. Verify `ws.isConnected === true`
2. Check conditional logic in useEffect
3. Ensure interval is cleared when connected

## Security Considerations

### Token Handling
- Token passed as query parameter (visible in logs)
- Consider connection-level auth after initial handshake
- Rotate tokens periodically

### Message Validation
- Always validate message types
- Sanitize data before rendering
- Use TypeScript for type safety

### Connection Limits
- Backend should limit connections per user
- Prevent abuse with rate limiting
- Monitor connection metrics

## Next Steps

### Phase 1: Infrastructure (Complete)
- ✅ useWebSocket hook with reconnection
- ✅ ConnectionStatus UI component
- ✅ Integration examples and documentation

### Phase 2: Page Integration (Pending)
- [ ] Integrate into DashboardPage
- [ ] Integrate into EventsPage
- [ ] Add to SendEventSheet for optimistic updates
- [ ] Test with real backend

### Phase 3: Enhancement (Future)
- [ ] Connection quality metrics
- [ ] Advanced error handling
- [ ] Message queuing during disconnection
- [ ] Multi-channel subscriptions
- [ ] WebSocket session persistence

## Additional Resources

- [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [AWS API Gateway WebSocket](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html)
- [React Hooks Best Practices](https://react.dev/reference/react)

## Support

For issues or questions:
1. Check this documentation
2. Review integration examples in `useWebSocket.example.tsx`
3. Check browser console for errors
4. Test connection with wscat
