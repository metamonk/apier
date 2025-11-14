/**
 * Send Event Sheet Component
 * Slide-over sheet for sending events from the dashboard
 * Triggers dashboard refresh on successful event creation
 */

import { useState } from 'react'
import { Button } from '../ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '../ui/sheet'
import { Send } from 'lucide-react'
import EventForm from '../EventForm'

interface SendEventSheetProps {
  onEventSent?: () => void
}

export function SendEventSheet({ onEventSent }: SendEventSheetProps) {
  const [isOpen, setIsOpen] = useState(false)

  const handleEventCreated = (event: any) => {
    console.log('Event created:', event)
    // Trigger dashboard refresh if callback provided
    if (onEventSent) {
      onEventSent()
    }
    // Auto-close sheet after successful event creation (with small delay for user feedback)
    setTimeout(() => {
      setIsOpen(false)
    }, 2000)
  }

  const handleError = (error: string) => {
    console.error('Event creation error:', error)
    // Keep sheet open on error so user can fix and retry
  }

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button className="gap-2">
          <Send className="h-4 w-4" />
          Send Event
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle>Send Event</SheetTitle>
          <SheetDescription>
            Create and send a new event to the API. Choose a preset event type or create a custom
            event with your own payload.
          </SheetDescription>
        </SheetHeader>

        <EventForm onEventCreated={handleEventCreated} onError={handleError} />
      </SheetContent>
    </Sheet>
  )
}
