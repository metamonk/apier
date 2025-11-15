/**
 * Events API Client
 * Handles all event-related API calls
 */

import type { Event, EventFilters } from './event-types'

const API_URL = import.meta.env.VITE_API_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

/**
 * Fetch events from /events endpoint with optional filters
 */
export async function fetchEvents(
  token: string,
  filters?: EventFilters
): Promise<Event[]> {
  const url = new URL(`${API_URL}/events`)

  // Use server-side status filtering if provided
  if (filters?.status) {
    url.searchParams.set('status_filter', filters.status)
  }

  const response = await fetch(url.toString(), {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.statusText}`)
  }

  const events = await response.json()

  // Client-side filtering for remaining filters
  let filteredEvents = events as Event[]

  if (filters) {
    if (filters.event_type) {
      filteredEvents = filteredEvents.filter(e => e.type === filters.event_type)
    }
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      filteredEvents = filteredEvents.filter(e =>
        e.id.toLowerCase().includes(searchLower) ||
        e.type.toLowerCase().includes(searchLower) ||
        JSON.stringify(e.payload).toLowerCase().includes(searchLower)
      )
    }
    if (filters.start_date) {
      filteredEvents = filteredEvents.filter(e => e.created_at >= filters.start_date!)
    }
    if (filters.end_date) {
      filteredEvents = filteredEvents.filter(e => e.created_at <= filters.end_date!)
    }
  }

  return filteredEvents
}

/**
 * Delete an event by ID
 */
export async function deleteEvent(token: string, eventId: string): Promise<void> {
  const response = await fetch(`${API_URL}/events/${eventId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Failed to delete event')
  }
}

/**
 * Export events to CSV or JSON
 */
export async function exportEvents(
  token: string,
  format: 'json' | 'csv',
  filters?: EventFilters
): Promise<Blob> {
  const url = new URL(`${API_URL}/events/export`)
  url.searchParams.set('format', format)

  if (filters) {
    if (filters.start_date) url.searchParams.set('start_date', filters.start_date)
    if (filters.end_date) url.searchParams.set('end_date', filters.end_date)
    if (filters.event_type) url.searchParams.set('event_type', filters.event_type)
  }

  const response = await fetch(url.toString(), {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to export events: ${response.statusText}`)
  }

  return await response.blob()
}

/**
 * Helper to download a blob as a file
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}
