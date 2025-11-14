/**
 * Export Button Component
 * Triggers CSV or JSON export of events
 */

import { useState } from 'react'
import { Button } from '../ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select'
import { Download, Loader2 } from 'lucide-react'
import { exportEvents, downloadBlob } from '../../lib/events-client'
import type { EventFilters } from '../../lib/event-types'

interface ExportButtonProps {
  token: string
  filters?: EventFilters
  disabled?: boolean
}

export function ExportButton({ token, filters, disabled }: ExportButtonProps) {
  const [format, setFormat] = useState<'json' | 'csv'>('json')
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async () => {
    try {
      setExporting(true)
      setError(null)

      const blob = await exportEvents(token, format, filters)
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
      const filename = `events_export_${timestamp}.${format}`

      downloadBlob(blob, filename)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
      console.error('Export error:', err)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Select value={format} onValueChange={(v) => setFormat(v as 'json' | 'csv')}>
        <SelectTrigger className="w-28 h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="json">JSON</SelectItem>
          <SelectItem value="csv">CSV</SelectItem>
        </SelectContent>
      </Select>

      <Button
        onClick={handleExport}
        disabled={disabled || exporting}
        size="sm"
        className="gap-2"
      >
        {exporting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Download className="h-4 w-4" />
        )}
        Export
      </Button>

      {error && (
        <div className="text-xs text-destructive">
          {error}
        </div>
      )}
    </div>
  )
}
