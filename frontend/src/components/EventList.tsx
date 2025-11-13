interface Event {
  id: string
  event_type: string
  payload: any
  status: string
  created_at: string
  updated_at: string
}

interface EventListProps {
  events: Event[]
  isPolling: boolean
}

function EventList({ events, isPolling }: EventListProps) {
  if (events.length === 0) {
    return (
      <div className="empty-state">
        <p>
          {isPolling ? '🔄 Polling for events...' : 'No events yet. Create your first event above!'}
        </p>
      </div>
    )
  }

  return (
    <div className="events-list">
      {events.map((event) => (
        <div key={event.id} className="event-card">
          <div className="event-header">
            <h3>{event.event_type}</h3>
            <span className={`status-badge ${event.status}`}>
              {event.status}
            </span>
          </div>
          <div className="event-details">
            <p className="event-id"><strong>ID:</strong> <code>{event.id}</code></p>
            <p className="event-time">
              <strong>Created:</strong> {new Date(event.created_at).toLocaleString()}
            </p>
            {event.updated_at !== event.created_at && (
              <p className="event-time">
                <strong>Updated:</strong> {new Date(event.updated_at).toLocaleString()}
              </p>
            )}
          </div>
          <details className="event-payload">
            <summary>View Payload</summary>
            <pre>{JSON.stringify(event.payload, null, 2)}</pre>
          </details>
        </div>
      ))}
    </div>
  )
}

export default EventList
