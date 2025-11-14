/**
 * Event Detail Modal Component
 * Shows full event details with JSON payload display
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Copy, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import type { Event } from '../../lib/event-types'

interface EventDetailModalProps {
  event: Event | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EventDetailModal({ event, open, onOpenChange }: EventDetailModalProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null)

  if (!event) return null

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text)
    setCopiedField(field)
    setTimeout(() => setCopiedField(null), 2000)
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'delivered':
        return 'default'
      case 'pending':
        return 'secondary'
      case 'failed':
        return 'destructive'
      default:
        return 'outline'
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <DialogTitle className="text-xl font-semibold mb-2">
                Event Details
              </DialogTitle>
              <DialogDescription className="font-mono text-xs break-all">
                {event.id}
              </DialogDescription>
            </div>
            <Badge variant={getStatusVariant(event.status)} className="shrink-0">
              {event.status}
            </Badge>
          </div>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Basic Information */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Basic Information
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Event Type</div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="font-mono">
                    {event.type}
                  </Badge>
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Source</div>
                <div className="text-sm font-mono">{event.source || 'N/A'}</div>
              </div>
            </div>
          </div>

          {/* Timestamps */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Timestamps
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Created At</div>
                <div className="text-sm">
                  {new Date(event.created_at).toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5 font-mono">
                  {event.created_at}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Updated At</div>
                <div className="text-sm">
                  {new Date(event.updated_at).toLocaleString()}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5 font-mono">
                  {event.updated_at}
                </div>
              </div>
            </div>
          </div>

          {/* Delivery Information */}
          {(event.delivery_attempts !== undefined || event.webhook_url) && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Delivery Information
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {event.delivery_attempts !== undefined && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">
                      Delivery Attempts
                    </div>
                    <div className="text-sm font-mono">{event.delivery_attempts}</div>
                  </div>
                )}
                {event.last_delivery_attempt && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">
                      Last Attempt
                    </div>
                    <div className="text-sm">
                      {new Date(event.last_delivery_attempt).toLocaleString()}
                    </div>
                  </div>
                )}
                {event.delivery_latency_ms !== undefined && event.delivery_latency_ms !== null && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">
                      Delivery Latency
                    </div>
                    <div className="text-sm font-mono">{event.delivery_latency_ms}ms</div>
                  </div>
                )}
                {event.webhook_url && (
                  <div className="sm:col-span-2">
                    <div className="text-xs text-muted-foreground mb-1">Webhook URL</div>
                    <div className="flex items-center gap-2">
                      <code className="text-xs bg-muted px-2 py-1 rounded flex-1 truncate">
                        {event.webhook_url}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.open(event.webhook_url, '_blank')}
                        className="shrink-0"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error Information */}
          {(event.error_message || event.last_error) && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Error Information
              </h3>
              <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
                <pre className="text-xs text-destructive whitespace-pre-wrap break-all">
                  {event.error_message || event.last_error}
                </pre>
              </div>
            </div>
          )}

          {/* Payload */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Payload
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  copyToClipboard(JSON.stringify(event.payload, null, 2), 'payload')
                }
                className="h-8 gap-2"
              >
                <Copy className="h-3 w-3" />
                {copiedField === 'payload' ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <div className="relative">
              <pre className="p-4 rounded-lg bg-muted text-xs overflow-x-auto max-h-96 overflow-y-auto">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </div>
          </div>

          {/* Full Event JSON */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Full Event JSON
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  copyToClipboard(JSON.stringify(event, null, 2), 'full')
                }
                className="h-8 gap-2"
              >
                <Copy className="h-3 w-3" />
                {copiedField === 'full' ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <div className="relative">
              <pre className="p-4 rounded-lg bg-muted text-xs overflow-x-auto max-h-96 overflow-y-auto">
                {JSON.stringify(event, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
