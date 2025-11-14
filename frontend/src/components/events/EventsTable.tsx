/**
 * Events Table Component
 * Displays events in a table with pagination and actions
 */

import { useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  Trash2,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import type { Event } from '../../lib/event-types'
import { deleteEvent } from '../../lib/events-client'

interface EventsTableProps {
  events: Event[]
  loading: boolean
  onEventClick: (event: Event) => void
  onEventsChange: () => void
  token: string
}

const ITEMS_PER_PAGE = 20

export function EventsTable({
  events,
  loading,
  onEventClick,
  onEventsChange,
  token,
}: EventsTableProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const totalPages = Math.ceil(events.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const paginatedEvents = events.slice(startIndex, endIndex)

  const handleDelete = async (eventId: string, eventType: string) => {
    if (!confirm(`Are you sure you want to delete this event?\n\nType: ${eventType}\nID: ${eventId}`)) {
      return
    }

    try {
      setDeletingId(eventId)
      setDeleteError(null)
      await deleteEvent(token, eventId)
      onEventsChange()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete event')
      console.error('Delete error:', err)
    } finally {
      setDeletingId(null)
    }
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

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <div className="rounded-full bg-muted p-3 mb-4">
          <AlertCircle className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">No events found</h3>
        <p className="text-sm text-muted-foreground">
          Try adjusting your filters or create a new event
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {deleteError && (
        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
          <div className="text-sm text-destructive">{deleteError}</div>
        </div>
      )}

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead>Event Type</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="w-[100px] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedEvents.map((event) => (
              <TableRow key={event.id}>
                <TableCell>
                  <Badge variant={getStatusVariant(event.status)}>
                    {event.status}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{event.type}</TableCell>
                <TableCell className="text-sm">{event.source || 'N/A'}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDate(event.created_at)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDate(event.updated_at)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEventClick(event)}
                      title="View details"
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(event.id, event.type)}
                      disabled={deletingId === event.id}
                      title="Delete event"
                      className="text-destructive hover:text-destructive"
                    >
                      {deletingId === event.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {startIndex + 1}-{Math.min(endIndex, events.length)} of{' '}
            {events.length} events
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <div className="text-sm text-muted-foreground">
              Page {currentPage} of {totalPages}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
