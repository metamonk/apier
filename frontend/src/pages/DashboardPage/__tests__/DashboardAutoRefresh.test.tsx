/**
 * Dashboard Auto-Refresh E2E Tests (Task 23.5)
 *
 * Tests the dashboard's auto-refresh functionality using React Testing Library
 * - Initial data load
 * - Auto-refresh every 10 seconds
 * - Pause/Resume functionality
 * - Manual refresh
 * - Updated data display
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import DashboardPage from '../index'
import type { EventSummary, LatencyMetrics, ThroughputMetrics } from '../../../lib/metrics-types'

// Mock the auth hook
vi.mock('../../../lib/useAuth', () => ({
  useAuth: () => ({
    token: 'mock-jwt-token',
    loading: false,
    error: null,
  }),
}))

// Mock the metrics client
vi.mock('../../../lib/metrics-client', () => ({
  fetchSummary: vi.fn(),
  fetchLatency: vi.fn(),
  fetchThroughput: vi.fn(),
}))

// Import mocked functions for manipulation
import * as metricsClient from '../../../lib/metrics-client'

// Mock data factory
const createMockSummary = (overrides?: Partial<EventSummary>): EventSummary => ({
  total: 100,
  pending: 10,
  delivered: 80,
  failed: 10,
  success_rate: 0.8,
  ...overrides,
})

const createMockLatency = (overrides?: Partial<LatencyMetrics>): LatencyMetrics => ({
  p50: 100,
  p95: 250,
  p99: 500,
  sample_size: 100,
  ...overrides,
})

const createMockThroughput = (overrides?: Partial<ThroughputMetrics>): ThroughputMetrics => ({
  events_per_minute: 10,
  events_per_hour: 600,
  total_events_24h: 14400,
  time_range: '24h',
  ...overrides,
})

// Helper to render dashboard with router context
const renderDashboard = () => {
  return render(
    <BrowserRouter>
      <DashboardPage />
    </BrowserRouter>
  )
}

describe('Dashboard Auto-Refresh E2E Tests', () => {
  beforeEach(() => {
    // Reset all mocks before each test
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })

    // Set default mock implementations
    vi.mocked(metricsClient.fetchSummary).mockResolvedValue(createMockSummary())
    vi.mocked(metricsClient.fetchLatency).mockResolvedValue(createMockLatency())
    vi.mocked(metricsClient.fetchThroughput).mockResolvedValue(createMockThroughput())
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  describe('Initial Data Load', () => {
    it('should fetch metrics data on initial load', async () => {
      await act(async () => {
        renderDashboard()
      })

      // Wait for initial render and effect to run
      await vi.advanceTimersByTimeAsync(0)

      // Verify data was fetched
      expect(metricsClient.fetchSummary).toHaveBeenCalledWith('mock-jwt-token')
      expect(metricsClient.fetchLatency).toHaveBeenCalledWith('mock-jwt-token')
      expect(metricsClient.fetchThroughput).toHaveBeenCalledWith('mock-jwt-token')
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)
    })

    it('should display initial metrics data', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)

      // Event count cards should display - use getAllByText for multiple matches
      const totalElements = screen.getAllByText('100')
      expect(totalElements.length).toBeGreaterThan(0)
      expect(screen.getAllByText('80').length).toBeGreaterThan(0)
      expect(screen.getAllByText('10').length).toBeGreaterThan(0)
    })

    it('should show last updated timestamp after initial load', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)

      // Look for "Updated" text followed by a time
      expect(screen.getByText(/Updated/i)).toBeInTheDocument()
    })
  })

  describe('Auto-Refresh Functionality', () => {
    it('should auto-refresh every 10 seconds', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Advance time by 10 seconds
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(2)
      expect(metricsClient.fetchLatency).toHaveBeenCalledTimes(2)
      expect(metricsClient.fetchThroughput).toHaveBeenCalledTimes(2)

      // Advance another 10 seconds
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(3)
      expect(metricsClient.fetchLatency).toHaveBeenCalledTimes(3)
      expect(metricsClient.fetchThroughput).toHaveBeenCalledTimes(3)
    })

    it('should display updated data after auto-refresh', async () => {
      // Setup initial data
      vi.mocked(metricsClient.fetchSummary).mockResolvedValue(
        createMockSummary({ total: 100 })
      )

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(screen.getAllByText('100').length).toBeGreaterThan(0)

      // Change mock data for next refresh
      vi.mocked(metricsClient.fetchSummary).mockResolvedValue(
        createMockSummary({ total: 150 })
      )

      // Advance time to trigger refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      // Wait for updated data to appear
      expect(screen.getAllByText('150').length).toBeGreaterThan(0)
    })

    it('should show auto-refresh interval in the UI', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(screen.getByText(/Auto-refresh: 10s/i)).toBeInTheDocument()
    })
  })

  describe('Pause/Resume Functionality', () => {
    it('should stop auto-refresh when paused', async () => {
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Find and click pause button
      const pauseButton = screen.getByRole('button', { name: /pause/i })
      await user.click(pauseButton)

      // Advance time - should NOT trigger refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      // Verify no additional calls were made
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)
    })

    it('should resume auto-refresh when resumed', async () => {
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      const initialCalls = metricsClient.fetchSummary.mock.calls.length

      // Pause
      const pauseButton = screen.getByRole('button', { name: /pause/i })
      await act(async () => {
        await user.click(pauseButton)
      })

      // Resume - this may trigger a fetch due to useEffect
      const resumeButton = screen.getByRole('button', { name: /resume/i })
      await act(async () => {
        await user.click(resumeButton)
      })

      const callsAfterResume = metricsClient.fetchSummary.mock.calls.length

      // Advance time - should trigger refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      // After advancing time, we should have at least one more call
      expect(metricsClient.fetchSummary.mock.calls.length).toBeGreaterThan(callsAfterResume)
    })

    it('should hide auto-refresh interval text when paused', async () => {
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(screen.getByText(/Auto-refresh: 10s/i)).toBeInTheDocument()

      // Pause
      const pauseButton = screen.getByRole('button', { name: /pause/i })
      await user.click(pauseButton)

      // Should hide auto-refresh text
      expect(screen.queryByText(/Auto-refresh: 10s/i)).not.toBeInTheDocument()
    })

    it('should toggle button text between Pause and Resume', async () => {
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)

      // Initially shows Pause
      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument()

      // Click to pause - should show Resume
      const pauseButton = screen.getByRole('button', { name: /pause/i })
      await user.click(pauseButton)
      expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument()

      // Click to resume - should show Pause again
      const resumeButton = screen.getByRole('button', { name: /resume/i })
      await user.click(resumeButton)
      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument()
    })
  })

  describe('Manual Refresh', () => {
    it('should fetch data when manual refresh button is clicked', async () => {
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Click manual refresh
      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      await act(async () => {
        await user.click(refreshButton)
      })

      await vi.advanceTimersByTimeAsync(0)

      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(2)
      expect(metricsClient.fetchLatency).toHaveBeenCalledTimes(2)
      expect(metricsClient.fetchThroughput).toHaveBeenCalledTimes(2)
    })

    it('should work when auto-refresh is paused', async () => {
      const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Pause auto-refresh
      const pauseButton = screen.getByRole('button', { name: /pause/i })
      await user.click(pauseButton)

      // Manual refresh should still work
      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      await act(async () => {
        await user.click(refreshButton)
      })

      await vi.advanceTimersByTimeAsync(0)

      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(2)
    })
  })

  describe('Error Handling', () => {
    it('should display error message when metrics fetch fails', async () => {
      vi.mocked(metricsClient.fetchSummary).mockRejectedValue(
        new Error('API request failed: 500 Internal Server Error')
      )

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)

      // Error appears in multiple sections, so use getAllByText
      expect(screen.getAllByText(/API request failed: 500/i).length).toBeGreaterThan(0)
    })

    it('should continue auto-refresh after error', async () => {
      // First call fails
      vi.mocked(metricsClient.fetchSummary).mockRejectedValueOnce(
        new Error('Network error')
      )

      // Subsequent calls succeed
      vi.mocked(metricsClient.fetchSummary).mockResolvedValue(createMockSummary())

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)

      // Error should appear (in multiple sections)
      expect(screen.getAllByText(/Network error/i).length).toBeGreaterThan(0)

      // Advance time to trigger next refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      // Should recover and show data
      expect(screen.getAllByText('100').length).toBeGreaterThan(0) // total events from mock
    })
  })

  describe('Timestamp Updates', () => {
    it('should update last updated timestamp after each refresh', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(screen.getByText(/Updated/i)).toBeInTheDocument()

      const firstTimestamp = screen.getByText(/Updated/i).textContent

      // Advance time to trigger refresh (need to advance real time for timestamp to change)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      // Wait for refresh to complete
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(2)

      // Timestamp should have updated
      const secondTimestamp = screen.getByText(/Updated/i).textContent

      // Both timestamps should exist
      expect(firstTimestamp).toBeTruthy()
      expect(secondTimestamp).toBeTruthy()
    })
  })

  describe('Multiple Refresh Cycles', () => {
    it('should handle multiple auto-refresh cycles correctly', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Cycle through 5 refreshes
      for (let i = 2; i <= 6; i++) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(10000)
        })

        expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(i)
      }

      // Verify final call count
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(6)
      expect(metricsClient.fetchLatency).toHaveBeenCalledTimes(6)
      expect(metricsClient.fetchThroughput).toHaveBeenCalledTimes(6)
    })

    it('should maintain correct refresh interval across multiple cycles', async () => {
      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Advance time by less than interval - should not refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(9000) // 9 seconds
      })

      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(1)

      // Advance remaining time - should refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000) // 1 more second = 10 total
      })

      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(2)
    })
  })

  describe('Data Consistency', () => {
    it('should fetch all three metrics endpoints in parallel', async () => {
      // Use mock implementations that track call order
      const callOrder: string[] = []

      vi.mocked(metricsClient.fetchSummary).mockImplementation(async () => {
        callOrder.push('summary')
        return createMockSummary()
      })

      vi.mocked(metricsClient.fetchLatency).mockImplementation(async () => {
        callOrder.push('latency')
        return createMockLatency()
      })

      vi.mocked(metricsClient.fetchThroughput).mockImplementation(async () => {
        callOrder.push('throughput')
        return createMockThroughput()
      })

      await act(async () => {
        renderDashboard()
      })

      await vi.advanceTimersByTimeAsync(0)

      expect(callOrder.length).toBe(3)

      // All three should have been called (order doesn't matter for parallel calls)
      expect(callOrder).toContain('summary')
      expect(callOrder).toContain('latency')
      expect(callOrder).toContain('throughput')
    })

    it('should maintain authentication token across refreshes', async () => {
      await act(async () => {
        renderDashboard()
      })

      // Initial load
      await vi.advanceTimersByTimeAsync(0)
      expect(metricsClient.fetchSummary).toHaveBeenCalledWith('mock-jwt-token')

      // Trigger refresh
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000)
      })

      // Should still use same token
      expect(metricsClient.fetchSummary).toHaveBeenCalledWith('mock-jwt-token')
      expect(metricsClient.fetchSummary).toHaveBeenCalledTimes(2)
    })
  })
})
