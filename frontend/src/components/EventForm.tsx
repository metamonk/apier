import { useState } from 'react'
import type { FormEvent } from 'react'

interface EventFormProps {
  onEventCreated: (event: any) => void
  onError: (error: string) => void
}

function EventForm({ onEventCreated, onError }: EventFormProps) {
  const [eventType, setEventType] = useState('user.signup')
  const [payload, setPayload] = useState('{\n  "user_id": "12345",\n  "email": "user@example.com",\n  "name": "John Doe"\n}')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

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
          event_type: eventType,
          payload: parsedPayload,
        }),
      })

      if (!eventResponse.ok) {
        const errorData = await eventResponse.json()
        throw new Error(errorData.detail || 'Failed to create event')
      }

      const eventData = await eventResponse.json()
      onEventCreated(eventData)

    } catch (err: any) {
      onError(err.message || 'An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handlePresetExample = (preset: string) => {
    switch (preset) {
      case 'signup':
        setEventType('user.signup')
        setPayload('{\n  "user_id": "12345",\n  "email": "user@example.com",\n  "name": "John Doe"\n}')
        break
      case 'purchase':
        setEventType('order.completed')
        setPayload('{\n  "order_id": "ORD-98765",\n  "user_id": "12345",\n  "total": 99.99,\n  "items": ["Product A", "Product B"]\n}')
        break
      case 'custom':
        setEventType('custom.event')
        setPayload('{\n  "data": "your custom data here"\n}')
        break
    }
  }

  return (
    <form onSubmit={handleSubmit} className="event-form">
      <div className="form-group">
        <label htmlFor="eventType">Event Type</label>
        <input
          id="eventType"
          type="text"
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
          placeholder="e.g., user.signup, order.completed"
          required
        />
        <div className="preset-buttons">
          <button type="button" onClick={() => handlePresetExample('signup')} className="preset-btn">
            📝 User Signup
          </button>
          <button type="button" onClick={() => handlePresetExample('purchase')} className="preset-btn">
            🛒 Order Completed
          </button>
          <button type="button" onClick={() => handlePresetExample('custom')} className="preset-btn">
            ⚡ Custom Event
          </button>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="payload">Payload (JSON)</label>
        <textarea
          id="payload"
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          placeholder='{ "key": "value" }'
          rows={10}
          required
          className="payload-textarea"
        />
      </div>

      <button type="submit" disabled={isSubmitting} className="submit-btn">
        {isSubmitting ? '⏳ Sending...' : '🚀 Send Event'}
      </button>
    </form>
  )
}

export default EventForm
