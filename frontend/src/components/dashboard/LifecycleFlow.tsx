/**
 * Event Lifecycle Flow Visualization
 * Shows the flow of events through the system: Ingested → Pending → Delivered
 */

import { ArrowRight } from 'lucide-react'
import type { EventSummary } from '../../lib/metrics-types'

interface LifecycleFlowProps {
  summary: EventSummary | null
  loading?: boolean
}

interface FlowStage {
  label: string
  count: number
  description: string
  color: string
  bgColor: string
}

export function LifecycleFlow({ summary, loading }: LifecycleFlowProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-4 py-8">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="animate-pulse">
            {i % 2 === 0 ? (
              <div className="h-24 w-32 bg-muted rounded-lg" />
            ) : (
              <div className="h-6 w-8 bg-muted rounded" />
            )}
          </div>
        ))}
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="p-6 rounded-lg border border-dashed border-border bg-muted/50 text-center">
        <p className="text-sm text-muted-foreground">No lifecycle data available</p>
      </div>
    )
  }

  const completed = summary.delivered + summary.failed

  const stages: FlowStage[] = [
    {
      label: 'Ingested',
      count: summary.total,
      description: 'Total events received',
      color: 'text-blue-600 dark:text-blue-400',
      bgColor: 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800',
    },
    {
      label: 'Pending',
      count: summary.pending,
      description: 'Awaiting delivery',
      color: 'text-yellow-600 dark:text-yellow-400',
      bgColor: 'bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800',
    },
    {
      label: 'Delivered',
      count: completed,
      description: 'Delivery attempted',
      color: 'text-green-600 dark:text-green-400',
      bgColor: 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800',
    },
  ]

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center justify-center gap-4 py-4 min-w-max">
        {stages.map((stage, index) => (
          <div key={stage.label} className="flex items-center gap-4">
            {/* Stage Card */}
            <div className={`relative p-6 rounded-lg border ${stage.bgColor} min-w-[140px] transition-transform hover:scale-105`}>
              <div className="text-center">
                <p className="text-sm font-medium text-muted-foreground mb-2">
                  {stage.label}
                </p>
                <p className={`text-3xl font-bold ${stage.color} mb-1`}>
                  {stage.count.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  {stage.description}
                </p>
              </div>
            </div>

            {/* Arrow */}
            {index < stages.length - 1 && (
              <ArrowRight className="h-6 w-6 text-muted-foreground flex-shrink-0" />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
