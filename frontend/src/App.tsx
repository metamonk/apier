import { useState, useEffect } from 'react'
import EventForm from './components/EventForm'
import EventList from './components/EventList'
import './App.css'

interface Event {
  id: string
  event_type: string
  payload: any
  status: string
  created_at: string
  updated_at: string
}

function App() {
  const [events, setEvents] = useState<Event[]>([])
  const [isPolling, setIsPolling] = useState(false)
  const [lastResponse, setLastResponse] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const handleEventCreated = (event: Event) => {
    setLastResponse(event)
    setError(null)
    // Add to local events list
    setEvents(prev => [event, ...prev])
  }

  const handleError = (err: string) => {
    setError(err)
    setLastResponse(null)
  }

  const togglePolling = () => {
    setIsPolling(!isPolling)
  }

  useEffect(() => {
    if (!isPolling) return

    const interval = setInterval(async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL
        const apiKey = import.meta.env.VITE_API_KEY

        if (!apiUrl || !apiKey) {
          console.error('API URL or API Key not configured')
          return
        }

        // Get JWT token first (OAuth2 password flow)
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
          console.error('Failed to get token')
          return
        }

        const { access_token } = await tokenResponse.json()

        // Poll inbox
        const inboxResponse = await fetch(`${apiUrl}/inbox`, {
          headers: {
            'Authorization': `Bearer ${access_token}`,
          },
        })

        if (inboxResponse.ok) {
          const { events: inboxEvents } = await inboxResponse.json()
          setEvents(inboxEvents)
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 5000) // Poll every 5 seconds

    return () => clearInterval(interval)
  }, [isPolling])

  return (
    <div className="app">
      <header>
        <h1>📮 Zapier Event Sender</h1>
        <p className="subtitle">Send custom events to your Zapier triggers</p>
      </header>

      <main>
        <div className="container">
          <section className="form-section">
            <h2>Create Event</h2>
            <EventForm
              onEventCreated={handleEventCreated}
              onError={handleError}
            />
          </section>

          {error && (
            <section className="response-section error">
              <h3>❌ Error</h3>
              <pre>{error}</pre>
            </section>
          )}

          {lastResponse && (
            <section className="response-section success">
              <h3>✅ Event Created</h3>
              <div className="response-details">
                <p><strong>Event ID:</strong> {lastResponse.id}</p>
                <p><strong>Type:</strong> {lastResponse.event_type}</p>
                <p><strong>Status:</strong> <span className={`status-badge ${lastResponse.status}`}>{lastResponse.status}</span></p>
                <p><strong>Created:</strong> {new Date(lastResponse.created_at).toLocaleString()}</p>
              </div>
              <details>
                <summary>View Full Response</summary>
                <pre>{JSON.stringify(lastResponse, null, 2)}</pre>
              </details>
            </section>
          )}

          <section className="events-section">
            <div className="section-header">
              <h2>Inbox Events</h2>
              <button
                onClick={togglePolling}
                className={`poll-toggle ${isPolling ? 'active' : ''}`}
              >
                {isPolling ? '⏸️ Pause Polling' : '▶️ Start Polling'}
              </button>
            </div>
            <EventList events={events} isPolling={isPolling} />
          </section>
        </div>
      </main>

      <footer>
        <p>Built with React + AWS Amplify | API Status: <span className="status-dot">🟢</span></p>
      </footer>
    </div>
  )
}

export default App
