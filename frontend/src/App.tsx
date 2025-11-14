import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import EventsPage from './pages/EventsPage'
import WebhooksPage from './pages/WebhooksPage'
import './App.css'

/**
 * Main App Component with React Router
 *
 * Routes:
 * - / : Dashboard (landing page)
 * - /events : Events management UI (Task 26) ✅
 * - /webhooks : Webhook receiver UI (Task 25) ✅
 *
 * Auth flow is integrated at the page level via useAuth hook
 */

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/webhooks" element={<WebhooksPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
