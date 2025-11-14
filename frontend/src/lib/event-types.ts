/**
 * Event Data Types
 * Matches backend DynamoDB schema
 */

export interface Event {
  id: string
  type: string
  source: string
  payload: Record<string, any>
  status: 'pending' | 'delivered' | 'failed'
  created_at: string
  updated_at: string
  delivery_attempts?: number
  last_delivery_attempt?: string | null
  delivery_latency_ms?: number | null
  error_message?: string | null
  webhook_url?: string
  retry_count?: number
  last_error?: string
}

export interface EventFilters {
  event_type?: string
  status?: string
  start_date?: string
  end_date?: string
  search?: string
}

export interface PaginatedEvents {
  events: Event[]
  total: number
  page: number
  limit: number
  hasMore: boolean
}
