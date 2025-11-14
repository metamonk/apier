/**
 * Auth Hook
 * Manages JWT token authentication with the API
 * Follows the same pattern as EventForm.tsx
 */

import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'
const API_KEY = import.meta.env.VITE_API_KEY || ''

interface AuthState {
  token: string | null
  loading: boolean
  error: string | null
}

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>({
    token: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    async function getToken() {
      try {
        if (!API_KEY) {
          throw new Error('API Key not configured. Please check your .env file.')
        }

        const tokenResponse = await fetch(`${API_URL}/token`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams({
            username: 'api',
            password: API_KEY,
          }),
        })

        if (!tokenResponse.ok) {
          throw new Error('Failed to authenticate')
        }

        const tokenData = await tokenResponse.json()

        setAuthState({
          token: tokenData.access_token,
          loading: false,
          error: null,
        })
      } catch (err) {
        setAuthState({
          token: null,
          loading: false,
          error: err instanceof Error ? err.message : 'Authentication failed',
        })
      }
    }

    getToken()
  }, [])

  return authState
}
