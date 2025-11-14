/**
 * Event Count Cards Component
 * Displays real-time metrics in card format: Total, Pending, Delivered, Failed, Success Rate
 */

import { Badge } from '../ui/badge'
import type { EventSummary } from '../../lib/metrics-types'

interface EventCountCardsProps {
  summary: EventSummary | null
  loading?: boolean
}

export function EventCountCards({ summary, loading }: EventCountCardsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="p-6 rounded-lg border border-border bg-card animate-pulse">
            <div className="h-4 bg-muted rounded w-20 mb-3" />
            <div className="h-8 bg-muted rounded w-16 mb-2" />
            <div className="h-3 bg-muted rounded w-12" />
          </div>
        ))}
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="p-6 rounded-lg border border-dashed border-border bg-muted/50 text-center">
        <p className="text-sm text-muted-foreground">No metrics data available</p>
      </div>
    )
  }

  const cards = [
    {
      label: 'Total Events',
      value: summary.total,
      badge: null,
      color: 'text-foreground',
    },
    {
      label: 'Pending',
      value: summary.pending,
      badge: { variant: 'secondary' as const, text: 'Queued' },
      color: 'text-yellow-600 dark:text-yellow-400',
    },
    {
      label: 'Delivered',
      value: summary.delivered,
      badge: { variant: 'default' as const, text: 'Success' },
      color: 'text-green-600 dark:text-green-400',
    },
    {
      label: 'Failed',
      value: summary.failed,
      badge: { variant: 'destructive' as const, text: 'Error' },
      color: 'text-red-600 dark:text-red-400',
    },
    {
      label: 'Success Rate',
      value: `${summary.success_rate}%`,
      badge: null,
      color: summary.success_rate >= 95
        ? 'text-green-600 dark:text-green-400'
        : summary.success_rate >= 85
        ? 'text-yellow-600 dark:text-yellow-400'
        : 'text-red-600 dark:text-red-400',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="p-6 rounded-lg border border-border bg-card hover:shadow-lg transition-shadow"
        >
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-muted-foreground">{card.label}</p>
            {card.badge && (
              <Badge variant={card.badge.variant} className="text-xs">
                {card.badge.text}
              </Badge>
            )}
          </div>
          <p className={`text-3xl font-bold ${card.color}`}>
            {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
          </p>
        </div>
      ))}
    </div>
  )
}
