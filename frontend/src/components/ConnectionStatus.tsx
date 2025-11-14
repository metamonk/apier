/**
 * Connection Status Component
 * Displays WebSocket connection status with visual indicators
 *
 * Features:
 * - Connection status badge with color coding
 * - Reconnection countdown display
 * - Manual reconnect button
 * - Responsive design
 */

import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Wifi, WifiOff, RefreshCw, AlertCircle } from 'lucide-react'
import { WebSocketState } from '../lib/useWebSocket'
import { cn } from '../lib/utils'

export interface ConnectionStatusProps {
  state: WebSocketState
  reconnectAttempt?: number
  reconnectDelay?: number
  maxReconnectAttempts?: number
  lastError?: string | null
  onReconnect?: () => void
  className?: string
  showDetails?: boolean
}

export function ConnectionStatus({
  state,
  reconnectAttempt = 0,
  reconnectDelay = 0,
  maxReconnectAttempts = 10,
  lastError = null,
  onReconnect,
  className,
  showDetails = false,
}: ConnectionStatusProps) {
  // Calculate badge variant and icon based on state
  const getStatusConfig = () => {
    switch (state) {
      case WebSocketState.CONNECTED:
        return {
          variant: 'default' as const,
          icon: Wifi,
          label: 'Connected',
          color: 'text-green-600 dark:text-green-400',
          bgColor: 'bg-green-100 dark:bg-green-950',
          borderColor: 'border-green-300 dark:border-green-700',
        }
      case WebSocketState.CONNECTING:
        return {
          variant: 'secondary' as const,
          icon: RefreshCw,
          label: 'Connecting',
          color: 'text-blue-600 dark:text-blue-400',
          bgColor: 'bg-blue-100 dark:bg-blue-950',
          borderColor: 'border-blue-300 dark:border-blue-700',
          animate: true,
        }
      case WebSocketState.RECONNECTING:
        return {
          variant: 'secondary' as const,
          icon: RefreshCw,
          label: 'Reconnecting',
          color: 'text-yellow-600 dark:text-yellow-400',
          bgColor: 'bg-yellow-100 dark:bg-yellow-950',
          borderColor: 'border-yellow-300 dark:border-yellow-700',
          animate: true,
        }
      case WebSocketState.ERROR:
        return {
          variant: 'destructive' as const,
          icon: AlertCircle,
          label: 'Error',
          color: 'text-red-600 dark:text-red-400',
          bgColor: 'bg-red-100 dark:bg-red-950',
          borderColor: 'border-red-300 dark:border-red-700',
        }
      case WebSocketState.DISCONNECTED:
      default:
        return {
          variant: 'outline' as const,
          icon: WifiOff,
          label: 'Disconnected',
          color: 'text-gray-600 dark:text-gray-400',
          bgColor: 'bg-gray-100 dark:bg-gray-900',
          borderColor: 'border-gray-300 dark:border-gray-700',
        }
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  // Calculate countdown for reconnection
  const reconnectCountdown = reconnectDelay > 0 ? Math.ceil(reconnectDelay / 1000) : 0

  // Show reconnect button if disconnected or error
  const showReconnectButton =
    (state === WebSocketState.DISCONNECTED || state === WebSocketState.ERROR) &&
    onReconnect

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {/* Status Badge */}
      <div
        className={cn(
          'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold',
          config.bgColor,
          config.borderColor,
          config.color
        )}
      >
        <Icon
          className={cn(
            'h-3.5 w-3.5',
            config.animate && 'animate-spin'
          )}
        />
        <span>{config.label}</span>
      </div>

      {/* Reconnection Details */}
      {showDetails && state === WebSocketState.RECONNECTING && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>
            Attempt {reconnectAttempt}/{maxReconnectAttempts}
          </span>
          {reconnectCountdown > 0 && (
            <span className="font-mono">
              ({reconnectCountdown}s)
            </span>
          )}
        </div>
      )}

      {/* Error Message */}
      {showDetails && lastError && state === WebSocketState.ERROR && (
        <span className="text-xs text-red-600 dark:text-red-400 max-w-[200px] truncate">
          {lastError}
        </span>
      )}

      {/* Manual Reconnect Button */}
      {showReconnectButton && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onReconnect}
          className="h-7 gap-1.5 text-xs"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </Button>
      )}
    </div>
  )
}
