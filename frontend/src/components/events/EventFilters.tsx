/**
 * Event Filters Component
 * Provides search and filter controls for events
 */

import { Input } from '../ui/input'
import { Label } from '../ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select'
import { Button } from '../ui/button'
import { X } from 'lucide-react'
import type { EventFilters as EventFiltersType } from '../../lib/event-types'

interface EventFiltersProps {
  filters: EventFiltersType
  onFiltersChange: (filters: EventFiltersType) => void
  eventTypes: string[]
}

export function EventFilters({ filters, onFiltersChange, eventTypes }: EventFiltersProps) {
  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, search: value || undefined })
  }

  const handleStatusChange = (value: string) => {
    onFiltersChange({ ...filters, status: value === 'all' ? undefined : value })
  }

  const handleEventTypeChange = (value: string) => {
    onFiltersChange({ ...filters, event_type: value === 'all' ? undefined : value })
  }

  const handleStartDateChange = (value: string) => {
    onFiltersChange({ ...filters, start_date: value || undefined })
  }

  const handleEndDateChange = (value: string) => {
    onFiltersChange({ ...filters, end_date: value || undefined })
  }

  const handleClearFilters = () => {
    onFiltersChange({})
  }

  const hasActiveFilters = Object.keys(filters).length > 0

  return (
    <div className="space-y-4 p-4 rounded-lg border bg-card">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Filters</h3>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearFilters}
            className="h-8 gap-2"
          >
            <X className="h-3 w-3" />
            Clear
          </Button>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {/* Search */}
        <div className="space-y-2">
          <Label htmlFor="search" className="text-xs">
            Search
          </Label>
          <Input
            id="search"
            placeholder="Event ID, payload..."
            value={filters.search || ''}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="h-9"
          />
        </div>

        {/* Status Filter */}
        <div className="space-y-2">
          <Label htmlFor="status" className="text-xs">
            Status
          </Label>
          <Select
            value={filters.status || 'all'}
            onValueChange={handleStatusChange}
          >
            <SelectTrigger id="status" className="h-9">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="delivered">Delivered</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Event Type Filter */}
        <div className="space-y-2">
          <Label htmlFor="event-type" className="text-xs">
            Event Type
          </Label>
          <Select
            value={filters.event_type || 'all'}
            onValueChange={handleEventTypeChange}
          >
            <SelectTrigger id="event-type" className="h-9">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {eventTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Start Date Filter */}
        <div className="space-y-2">
          <Label htmlFor="start-date" className="text-xs">
            Start Date
          </Label>
          <Input
            id="start-date"
            type="datetime-local"
            value={filters.start_date?.replace('Z', '').slice(0, 16) || ''}
            onChange={(e) => {
              const isoDate = e.target.value ? new Date(e.target.value).toISOString() : ''
              handleStartDateChange(isoDate)
            }}
            className="h-9"
          />
        </div>

        {/* End Date Filter */}
        <div className="space-y-2">
          <Label htmlFor="end-date" className="text-xs">
            End Date
          </Label>
          <Input
            id="end-date"
            type="datetime-local"
            value={filters.end_date?.replace('Z', '').slice(0, 16) || ''}
            onChange={(e) => {
              const isoDate = e.target.value ? new Date(e.target.value).toISOString() : ''
              handleEndDateChange(isoDate)
            }}
            className="h-9"
          />
        </div>
      </div>
    </div>
  )
}
