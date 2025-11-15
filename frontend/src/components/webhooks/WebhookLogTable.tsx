/**
 * WebhookLogTable Component
 * Displays webhook delivery logs in a table with expandable JSON payloads
 */

import { useState } from 'react'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react'
import type { WebhookLog } from '../../pages/WebhooksPage'

interface WebhookLogTableProps {
  logs: WebhookLog[]
  loading: boolean
}

export function WebhookLogTable({ logs, loading }: WebhookLogTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedRows(newExpanded)
  }

  const copyPayload = async (payload: Record<string, any>, id: string) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-3"></div>
          <p className="text-sm text-muted-foreground">Loading webhook logs...</p>
        </div>
      </div>
    )
  }

  if (logs.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-lg font-medium mb-2">No webhook deliveries found</p>
          <p className="text-sm text-muted-foreground">
            Webhook deliveries will appear here in real-time
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted/50 border-b">
            <tr>
              <th className="w-8 px-4 py-3"></th>
              <th className="px-4 py-3 text-left text-sm font-medium">Event ID</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Timestamp</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Event Type</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Source IP</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
              <th className="px-4 py-3 text-left text-sm font-medium">Request ID</th>
              <th className="w-24 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {logs.map((log) => {
              const isExpanded = expandedRows.has(log.id)
              return (
                <>
                  <tr key={log.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleRow(log.id)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground max-w-xs truncate" title={log.id}>
                      {log.id}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono whitespace-nowrap">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary" className="font-mono text-xs">
                        {log.event_type}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground">
                      {log.source_ip}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="default" className="bg-green-100 text-green-800 border-green-200 dark:bg-green-950 dark:text-green-100 dark:border-green-800">
                        {log.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-muted-foreground">
                      {log.request_id || '-'}
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyPayload(log.payload, log.id)}
                        className="gap-2"
                      >
                        {copiedId === log.id ? (
                          <>
                            <Check className="h-3 w-3" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3" />
                            Copy
                          </>
                        )}
                      </Button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${log.id}-details`} className="bg-muted/20">
                      <td colSpan={8} className="px-4 py-4">
                        <div className="space-y-3">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold">Payload</h4>
                          </div>
                          <pre className="bg-background border rounded-lg p-4 overflow-x-auto text-xs font-mono">
                            {JSON.stringify(log.payload, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
