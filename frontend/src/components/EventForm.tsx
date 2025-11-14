import { useState } from 'react'
import type { FormEvent } from 'react'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select'
import { Sparkles, Send, CheckCircle2, XCircle, Loader2, Wand2 } from 'lucide-react'
import { JsonEditor } from './JsonEditor'

interface EventFormProps {
  onEventCreated: (event: any) => void
  onError: (error: string) => void
}

type EventStatus = "idle" | "sending" | "success" | "error"

const EVENT_TYPES = [
  { value: "user.signup", label: "User Signup" },
  { value: "order.completed", label: "Order Completed" },
  { value: "payment.success", label: "Payment Success" },
  { value: "custom", label: "Custom Event" },
]

const DEFAULT_PAYLOADS: Record<string, any> = {
  "user.signup": {
    userId: "12345",
    email: "user@example.com",
    name: "John Doe",
    timestamp: new Date().toISOString(),
  },
  "order.completed": {
    orderId: "ORD-98765",
    userId: "12345",
    amount: 99.99,
    items: 3,
    timestamp: new Date().toISOString(),
  },
  "payment.success": {
    paymentId: "pay_abc123",
    amount: 149.5,
    currency: "USD",
    method: "card",
    timestamp: new Date().toISOString(),
  },
  custom: {
    event: "your.custom.event",
    data: {},
    timestamp: new Date().toISOString(),
  },
}

function EventForm({ onEventCreated, onError }: EventFormProps) {
  const [eventType, setEventType] = useState('user.signup')
  const [customEventType, setCustomEventType] = useState('')
  const [payload, setPayload] = useState(JSON.stringify(DEFAULT_PAYLOADS["user.signup"], null, 2))
  const [status, setStatus] = useState<EventStatus>("idle")
  const [errorMessage, setErrorMessage] = useState<string>("")
  const [isGenerating, setIsGenerating] = useState(false)

  const handleEventTypeChange = (value: string) => {
    setEventType(value)
    if (DEFAULT_PAYLOADS[value]) {
      setPayload(JSON.stringify(DEFAULT_PAYLOADS[value], null, 2))
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setStatus("sending")
    setErrorMessage("")

    try {
      const apiUrl = import.meta.env.VITE_API_URL
      const apiKey = import.meta.env.VITE_API_KEY

      if (!apiUrl || !apiKey) {
        throw new Error('API URL or API Key not configured. Please check your .env file.')
      }

      // Parse payload JSON
      let parsedPayload
      try {
        parsedPayload = JSON.parse(payload)
      } catch (err) {
        throw new Error('Invalid JSON payload. Please check your syntax.')
      }

      // Use custom event type if provided, otherwise use selected preset
      const finalEventType = customEventType || eventType

      // Step 1: Get JWT token (OAuth2 password flow)
      const tokenResponse = await fetch(`${apiUrl}/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: 'api',
          password: apiKey,
        }),
      })

      if (!tokenResponse.ok) {
        const errorData = await tokenResponse.json()
        throw new Error(errorData.detail || 'Failed to authenticate')
      }

      const { access_token } = await tokenResponse.json()

      // Step 2: Create event
      const eventResponse = await fetch(`${apiUrl}/events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${access_token}`,
        },
        body: JSON.stringify({
          type: finalEventType,
          source: 'sender-ui',
          payload: parsedPayload,
        }),
      })

      if (!eventResponse.ok) {
        const errorData = await eventResponse.json()
        throw new Error(errorData.detail || 'Failed to create event')
      }

      const eventData = await eventResponse.json()
      onEventCreated(eventData)
      setStatus("success")

      // Reset status after 3 seconds
      setTimeout(() => {
        setStatus("idle")
      }, 3000)

    } catch (err: any) {
      setStatus("error")
      setErrorMessage(err.message || 'An unexpected error occurred')
      onError(err.message || 'An unexpected error occurred')

      // Reset status after 4 seconds
      setTimeout(() => {
        setStatus("idle")
        setErrorMessage("")
      }, 4000)
    }
  }

  const handleGenerateEvent = async () => {
    setIsGenerating(true)

    try {
      const openaiApiKey = import.meta.env.VITE_OPENAI_API_KEY

      if (!openaiApiKey) {
        throw new Error('OpenAI API key not configured')
      }

      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${openaiApiKey}`
        },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [
            {
              role: 'system',
              content: 'You are an event generator that creates realistic business events with varied JSON structures. Generate diverse event types (user actions, e-commerce, subscriptions, analytics, notifications, support, payments, etc.) with appropriate complexity (simple objects, nested data, arrays).'
            },
            {
              role: 'user',
              content: 'Generate a single realistic business event. Include an event_type (e.g., "user.signup", "order.completed") and a payload object with realistic data. Vary the complexity - sometimes simple, sometimes with nested objects or arrays. Use realistic IDs, timestamps, and data.'
            }
          ],
          response_format: {
            type: 'json_schema',
            json_schema: {
              name: 'event_generation',
              schema: {
                type: 'object',
                properties: {
                  event_type: {
                    type: 'string',
                    description: 'The type of event (e.g., user.signup, order.completed)'
                  },
                  payload: {
                    type: 'object',
                    description: 'The event payload with realistic data'
                  }
                },
                required: ['event_type', 'payload'],
                additionalProperties: false
              }
            }
          },
          temperature: 1.2
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error?.message || 'Failed to generate event')
      }

      const data = await response.json()
      const generatedEvent = JSON.parse(data.choices[0].message.content)

      setCustomEventType(generatedEvent.event_type)
      setPayload(JSON.stringify(generatedEvent.payload, null, 2))
    } catch (err: any) {
      onError(err.message || 'Failed to generate event')
    } finally {
      setIsGenerating(false)
    }
  }

  const getStatusIcon = () => {
    switch (status) {
      case "sending":
        return <Loader2 className="h-4 w-4 animate-spin" />
      case "success":
        return <CheckCircle2 className="h-4 w-4" />
      case "error":
        return <XCircle className="h-4 w-4" />
      default:
        return <Send className="h-4 w-4" />
    }
  }

  const getStatusText = () => {
    switch (status) {
      case "sending":
        return "Sending..."
      case "success":
        return "Event Sent!"
      case "error":
        return "Failed to Send"
      default:
        return "Send Event"
    }
  }

  return (
    <Card className="border-border bg-card overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-6 py-4">
        <h2 className="font-semibold flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Event Configuration
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="p-6 space-y-6">
        {/* Event Type Configuration */}
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="event-select">Event Type</Label>
            <Select value={eventType} onValueChange={handleEventTypeChange}>
              <SelectTrigger id="event-select">
                <SelectValue placeholder="Select event type" />
              </SelectTrigger>
              <SelectContent>
                {EVENT_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Choose a preset event type or select "Custom Event" to define your own
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="custom-event">
              Custom Event Name
              <span className="ml-1 text-xs text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="custom-event"
              placeholder="e.g., user.logged_in"
              value={customEventType}
              onChange={(e) => setCustomEventType(e.target.value)}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Override the preset event type with your own custom event name
            </p>
          </div>

          {/* AI Generate Button */}
          <div className="pt-2">
            <Button
              type="button"
              variant="default"
              onClick={handleGenerateEvent}
              disabled={isGenerating}
              className="w-full gap-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" />
                  Generate Event with AI
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              Let AI create a realistic event with varied structure and data
            </p>
          </div>
        </div>

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-border"></div>
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-card px-2 text-muted-foreground">Payload Editor</span>
          </div>
        </div>

        {/* JSON Payload Editor */}
        <div className="space-y-2">
          <Label htmlFor="payload-editor">Event Payload (JSON)</Label>
          <JsonEditor value={payload} onChange={setPayload} />
          <p className="text-xs text-muted-foreground">
            Customize the event payload or use the generated/preset payload as-is
          </p>
        </div>

        {/* Status Messages */}
        {status === "error" && errorMessage && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 flex items-start gap-3">
            <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-destructive text-sm">Error sending event</p>
              <p className="text-destructive/80 text-sm mt-1">{errorMessage}</p>
            </div>
          </div>
        )}

        {status === "success" && (
          <div className="rounded-lg bg-success/10 border border-success/20 p-4 flex items-start gap-3">
            <CheckCircle2 className="h-5 w-5 text-success shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-success text-sm">Event sent successfully</p>
              <p className="text-success/80 text-sm mt-1">Your event has been triggered and is being processed</p>
            </div>
          </div>
        )}

        {/* Send Button */}
        <div className="pt-2">
          <Button
            type="submit"
            disabled={status === "sending"}
            className="w-full bg-green-600 hover:bg-green-700 text-white"
            size="lg"
          >
            {getStatusIcon()}
            <span className="ml-2">{getStatusText()}</span>
          </Button>
        </div>
      </form>
    </Card>
  )
}

export default EventForm
