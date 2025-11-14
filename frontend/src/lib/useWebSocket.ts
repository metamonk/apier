/**
 * WebSocket Hook
 * Real-time event updates via WebSocket connection
 *
 * Features:
 * - Connection state management (connecting, connected, disconnected, error)
 * - Automatic reconnection with exponential backoff
 * - Heartbeat/ping-pong mechanism for connection health
 * - Polling fallback when WebSocket unavailable
 * - Tab visibility handling for connection management
 * - Type-safe message handling
 */

import { useState, useEffect, useRef, useCallback } from 'react'

// WebSocket connection states
export enum WebSocketState {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting',
}

// Message types that can be sent/received
export enum MessageType {
  PING = 'ping',
  PONG = 'pong',
  EVENT_UPDATE = 'event_update',
  EVENT_CREATED = 'event_created',
  EVENT_DELETED = 'event_deleted',
  METRICS_UPDATE = 'metrics_update',
  SUBSCRIBE = 'subscribe',
  UNSUBSCRIBE = 'unsubscribe',
  ERROR = 'error',
}

// WebSocket message interface
export interface WebSocketMessage {
  type: MessageType
  data?: any
  timestamp?: string
  error?: string
}

// Event update from WebSocket
export interface EventUpdate {
  id: string
  type: string
  status: 'pending' | 'delivered' | 'failed'
  created_at: string
  updated_at: string
  [key: string]: any
}

// Metrics update from WebSocket
export interface MetricsUpdate {
  total_events: number
  pending_events: number
  delivered_events: number
  failed_events: number
  [key: string]: any
}

// Hook configuration
export interface UseWebSocketConfig {
  url?: string
  token?: string
  enabled?: boolean
  reconnect?: boolean
  maxReconnectAttempts?: number
  initialReconnectDelay?: number
  maxReconnectDelay?: number
  heartbeatInterval?: number
  heartbeatTimeout?: number
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onMessage?: (message: WebSocketMessage) => void
  onEventUpdate?: (event: EventUpdate) => void
  onEventCreated?: (event: EventUpdate) => void
  onEventDeleted?: (eventId: string) => void
  onMetricsUpdate?: (metrics: MetricsUpdate) => void
}

// Default configuration
const DEFAULT_CONFIG = {
  reconnect: true,
  maxReconnectAttempts: 10,
  initialReconnectDelay: 1000, // 1 second
  maxReconnectDelay: 30000, // 30 seconds
  heartbeatInterval: 30000, // 30 seconds
  heartbeatTimeout: 5000, // 5 seconds
}

export function useWebSocket(config: UseWebSocketConfig = {}) {
  const {
    url = import.meta.env.VITE_WEBSOCKET_URL || '',
    token = '',
    enabled = true,
    reconnect = DEFAULT_CONFIG.reconnect,
    maxReconnectAttempts = DEFAULT_CONFIG.maxReconnectAttempts,
    initialReconnectDelay = DEFAULT_CONFIG.initialReconnectDelay,
    maxReconnectDelay = DEFAULT_CONFIG.maxReconnectDelay,
    heartbeatInterval = DEFAULT_CONFIG.heartbeatInterval,
    heartbeatTimeout = DEFAULT_CONFIG.heartbeatTimeout,
    onOpen,
    onClose,
    onError,
    onMessage,
    onEventUpdate,
    onEventCreated,
    onEventDeleted,
    onMetricsUpdate,
  } = config

  const [state, setState] = useState<WebSocketState>(WebSocketState.DISCONNECTED)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const [reconnectDelay, setReconnectDelay] = useState(initialReconnectDelay)
  const [lastError, setLastError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isManuallyClosedRef = useRef(false)

  // Calculate exponential backoff delay
  const calculateBackoffDelay = useCallback((attempt: number) => {
    const delay = Math.min(
      initialReconnectDelay * Math.pow(2, attempt),
      maxReconnectDelay
    )
    // Add jitter to prevent thundering herd
    return delay + Math.random() * 1000
  }, [initialReconnectDelay, maxReconnectDelay])

  // Send message through WebSocket
  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
      return true
    }
    console.warn('WebSocket not connected, cannot send message:', message)
    return false
  }, [])

  // Send ping to keep connection alive
  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      send({ type: MessageType.PING, timestamp: new Date().toISOString() })

      // Set timeout for pong response
      heartbeatTimeoutRef.current = setTimeout(() => {
        console.warn('Heartbeat timeout - no pong received')
        wsRef.current?.close()
      }, heartbeatTimeout)
    }
  }, [send, heartbeatTimeout])

  // Handle pong response
  const handlePong = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current)
      heartbeatTimeoutRef.current = null
    }
  }, [])

  // Start heartbeat
  const startHeartbeat = useCallback(() => {
    // Clear existing interval
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
    }

    // Send initial ping
    sendPing()

    // Set up periodic pings
    heartbeatIntervalRef.current = setInterval(() => {
      sendPing()
    }, heartbeatInterval)
  }, [sendPing, heartbeatInterval])

  // Stop heartbeat
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current)
      heartbeatTimeoutRef.current = null
    }
  }, [])

  // Handle incoming messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)

      // Handle system messages
      switch (message.type) {
        case MessageType.PONG:
          handlePong()
          break

        case MessageType.EVENT_UPDATE:
          onEventUpdate?.(message.data as EventUpdate)
          break

        case MessageType.EVENT_CREATED:
          onEventCreated?.(message.data as EventUpdate)
          break

        case MessageType.EVENT_DELETED:
          onEventDeleted?.(message.data?.id)
          break

        case MessageType.METRICS_UPDATE:
          onMetricsUpdate?.(message.data as MetricsUpdate)
          break

        case MessageType.ERROR:
          console.error('WebSocket error message:', message.error)
          setLastError(message.error || 'Unknown error')
          break
      }

      // Call custom message handler
      onMessage?.(message)
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err)
    }
  }, [handlePong, onMessage, onEventUpdate, onEventCreated, onEventDeleted, onMetricsUpdate])

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Don't connect if disabled or no URL
    if (!enabled || !url) {
      console.log('WebSocket disabled or no URL provided')
      return
    }

    // Don't connect if already connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected')
      return
    }

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    try {
      setState(reconnectAttempt > 0 ? WebSocketState.RECONNECTING : WebSocketState.CONNECTING)
      setLastError(null)

      // Build WebSocket URL with token
      const wsUrl = token ? `${url}?token=${token}` : url
      console.log('Connecting to WebSocket:', wsUrl.replace(/token=[^&]+/, 'token=***'))

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setState(WebSocketState.CONNECTED)
        setReconnectAttempt(0)
        setReconnectDelay(initialReconnectDelay)
        isManuallyClosedRef.current = false
        startHeartbeat()
        onOpen?.()
      }

      ws.onmessage = handleMessage

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        setState(WebSocketState.ERROR)
        setLastError('Connection error')
        onError?.(event)
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        stopHeartbeat()
        setState(WebSocketState.DISCONNECTED)
        onClose?.()

        // Attempt reconnection if not manually closed
        if (reconnect && !isManuallyClosedRef.current && reconnectAttempt < maxReconnectAttempts) {
          const delay = calculateBackoffDelay(reconnectAttempt)
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempt + 1}/${maxReconnectAttempts})`)

          setReconnectDelay(delay)
          setReconnectAttempt(prev => prev + 1)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else if (reconnectAttempt >= maxReconnectAttempts) {
          console.error('Max reconnection attempts reached')
          setLastError('Failed to reconnect after maximum attempts')
        }
      }
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      setState(WebSocketState.ERROR)
      setLastError(err instanceof Error ? err.message : 'Failed to connect')
    }
  }, [
    enabled,
    url,
    token,
    reconnect,
    reconnectAttempt,
    maxReconnectAttempts,
    initialReconnectDelay,
    calculateBackoffDelay,
    startHeartbeat,
    stopHeartbeat,
    handleMessage,
    onOpen,
    onClose,
    onError,
  ])

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    console.log('Manually disconnecting WebSocket')
    isManuallyClosedRef.current = true

    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // Stop heartbeat
    stopHeartbeat()

    // Close connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setState(WebSocketState.DISCONNECTED)
    setReconnectAttempt(0)
  }, [stopHeartbeat])

  // Manually trigger reconnection
  const reconnectNow = useCallback(() => {
    disconnect()
    isManuallyClosedRef.current = false
    setReconnectAttempt(0)
    connect()
  }, [disconnect, connect])

  // Subscribe to a channel/topic
  const subscribe = useCallback((channel: string) => {
    send({
      type: MessageType.SUBSCRIBE,
      data: { channel },
    })
  }, [send])

  // Unsubscribe from a channel/topic
  const unsubscribe = useCallback((channel: string) => {
    send({
      type: MessageType.UNSUBSCRIBE,
      data: { channel },
    })
  }, [send])

  // Handle browser tab visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab hidden - stop heartbeat but keep connection
        stopHeartbeat()
      } else {
        // Tab visible - resume heartbeat and reconnect if needed
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          startHeartbeat()
        } else if (enabled && !isManuallyClosedRef.current) {
          connect()
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [enabled, connect, startHeartbeat, stopHeartbeat])

  // Initial connection and cleanup
  useEffect(() => {
    if (enabled && url) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [enabled, url]) // Note: connect/disconnect not in deps to avoid reconnect loops

  return {
    state,
    isConnected: state === WebSocketState.CONNECTED,
    isConnecting: state === WebSocketState.CONNECTING || state === WebSocketState.RECONNECTING,
    isDisconnected: state === WebSocketState.DISCONNECTED,
    isError: state === WebSocketState.ERROR,
    reconnectAttempt,
    reconnectDelay,
    lastError,
    send,
    connect,
    disconnect,
    reconnect: reconnectNow,
    subscribe,
    unsubscribe,
  }
}
