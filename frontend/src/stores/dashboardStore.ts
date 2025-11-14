/**
 * Dashboard Store - Unified Data Layer with Zustand
 * Single source of truth for all dashboard metrics
 *
 * Benefits over React Context:
 * - No Provider needed
 * - Better performance (no unnecessary re-renders)
 * - Can be accessed outside React components
 * - Simpler API with automatic shallow comparison
 * - All UI components derive from same state = no sync issues
 */

import { create } from 'zustand'
import type { EventSummary, LatencyMetrics, ThroughputMetrics } from '../lib/metrics-types'

interface DashboardState {
  // Data
  summary: EventSummary | null
  latency: LatencyMetrics | null
  throughput: ThroughputMetrics | null
  loading: boolean
  error: string | null
  lastUpdated: Date | null
}

interface DashboardActions {
  // Unified update for all metrics at once (API calls, WebSocket full updates)
  updateMetrics: (data: {
    summary?: EventSummary
    latency?: LatencyMetrics
    throughput?: ThroughputMetrics
  }) => void

  // Individual setters
  setSummary: (summary: EventSummary) => void
  setLatency: (latency: LatencyMetrics) => void
  setThroughput: (throughput: ThroughputMetrics) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void

  // Optimistic updates for WebSocket events
  optimisticEventCreated: () => void
  optimisticEventStatusChanged: (oldStatus: string, newStatus: string) => void
  optimisticEventDeleted: () => void
}

type DashboardStore = DashboardState & DashboardActions

export const useDashboardStore = create<DashboardStore>()((set) => ({
  // Initial state
  summary: null,
  latency: null,
  throughput: null,
  loading: false,
  error: null,
  lastUpdated: null,

  // Update all metrics at once - this ensures everything stays in sync
  updateMetrics: (data) =>
    set((state) => ({
      summary: data.summary ?? state.summary,
      latency: data.latency ?? state.latency,
      throughput: data.throughput ?? state.throughput,
      lastUpdated: new Date(),
    })),

  // Individual setters
  setSummary: (summary) =>
    set({
      summary,
      lastUpdated: new Date(),
    }),

  setLatency: (latency) =>
    set({
      latency,
      lastUpdated: new Date(),
    }),

  setThroughput: (throughput) =>
    set({
      throughput,
      lastUpdated: new Date(),
    }),

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error }),

  // Optimistic update when event is created
  optimisticEventCreated: () =>
    set((state) => {
      if (!state.summary) return state

      return {
        summary: {
          ...state.summary,
          total: state.summary.total + 1,
          pending: state.summary.pending + 1, // New events start as pending
        },
        throughput: state.throughput
          ? {
              ...state.throughput,
              total_events_24h: state.throughput.total_events_24h + 1,
            }
          : null,
        lastUpdated: new Date(),
      }
    }),

  // Optimistic update when event status changes
  optimisticEventStatusChanged: (oldStatus, newStatus) =>
    set((state) => {
      if (!state.summary) return state

      const updated = { ...state.summary }

      // Map status to summary field
      const statusFieldMap: Record<string, keyof EventSummary> = {
        pending: 'pending',
        delivered: 'delivered',
        failed: 'failed',
      }

      // Decrement old status count
      const oldField = statusFieldMap[oldStatus]
      if (oldField && typeof updated[oldField] === 'number') {
        updated[oldField] = Math.max(0, (updated[oldField] as number) - 1)
      }

      // Increment new status count
      const newField = statusFieldMap[newStatus]
      if (newField && typeof updated[newField] === 'number') {
        updated[newField] = (updated[newField] as number) + 1
      }

      // Recalculate success rate
      if (updated.total > 0) {
        updated.success_rate = Math.round((updated.delivered / updated.total) * 100)
      }

      return {
        summary: updated,
        lastUpdated: new Date(),
      }
    }),

  // Optimistic update when event is deleted
  optimisticEventDeleted: () =>
    set((state) => {
      if (!state.summary) return state

      return {
        summary: {
          ...state.summary,
          total: Math.max(0, state.summary.total - 1),
        },
        throughput: state.throughput
          ? {
              ...state.throughput,
              total_events_24h: Math.max(0, state.throughput.total_events_24h - 1),
            }
          : null,
        lastUpdated: new Date(),
      }
    }),
}))
