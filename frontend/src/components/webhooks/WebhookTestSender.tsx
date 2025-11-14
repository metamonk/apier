/**
 * WebhookTestSender Component
 * Tool for testing webhook deliveries with HMAC signature generation
 */

import { useState } from 'react'
import { Card } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Send, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { JsonEditor } from '../JsonEditor'

const API_URL = import.meta.env.VITE_API_URL || 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

interface WebhookTestSenderProps {
  onWebhookSent: () => void
}

type SendStatus = "idle" | "sending" | "success" | "error"

const DEFAULT_PAYLOAD = {
  user_id: "test-123",
  email: "test@example.com",
  timestamp: new Date().toISOString()
}

export function WebhookTestSender({ onWebhookSent }: WebhookTestSenderProps) {
  const [eventType, setEventType] = useState('test.webhook')
  const [payload, setPayload] = useState(JSON.stringify(DEFAULT_PAYLOAD, null, 2))
  const [webhookSecret, setWebhookSecret] = useState('')
  const [status, setStatus] = useState<SendStatus>("idle")
  const [errorMessage, setErrorMessage] = useState<string>("")
  const [responseData, setResponseData] = useState<any>(null)

  // Generate HMAC-SHA256 signature
  const generateHmacSignature = async (message: string, secret: string): Promise<string> => {
    const encoder = new TextEncoder()
    const keyData = encoder.encode(secret)
    const messageData = encoder.encode(message)

    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      keyData,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    )

    const signature = await crypto.subtle.sign('HMAC', cryptoKey, messageData)
    const hashArray = Array.from(new Uint8Array(signature))
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

    return hashHex
  }

  const handleSendWebhook = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus("sending")
    setErrorMessage("")
    setResponseData(null)

    try {
      // Parse payload JSON
      let parsedPayload
      try {
        parsedPayload = JSON.parse(payload)
      } catch (err) {
        throw new Error('Invalid JSON payload. Please check your syntax.')
      }

      // Build webhook request body
      const webhookBody = {
        event_type: eventType,
        event_id: `test-${Date.now()}`,
        payload: parsedPayload,
        timestamp: new Date().toISOString()
      }

      const bodyString = JSON.stringify(webhookBody)

      // Generate HMAC signature if secret is provided
      let signature = ''
      if (webhookSecret) {
        signature = await generateHmacSignature(bodyString, webhookSecret)
      }

      // Send webhook
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      }

      if (signature) {
        headers['X-Webhook-Signature'] = signature
      }

      const response = await fetch(`${API_URL}/webhook`, {
        method: 'POST',
        headers,
        body: bodyString,
      })

      const responseJson = await response.json()

      if (!response.ok) {
        throw new Error(responseJson.detail || 'Failed to send webhook')
      }

      setResponseData(responseJson)
      setStatus("success")
      onWebhookSent()

      // Reset status after 3 seconds
      setTimeout(() => {
        setStatus("idle")
        setResponseData(null)
      }, 3000)

    } catch (err: any) {
      setStatus("error")
      setErrorMessage(err.message || 'An unexpected error occurred')

      // Reset status after 4 seconds
      setTimeout(() => {
        setStatus("idle")
        setErrorMessage("")
      }, 4000)
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
        return "Sent!"
      case "error":
        return "Failed"
      default:
        return "Send Test Webhook"
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Send className="h-4 w-4 text-primary" />
          Test Webhook Sender
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          Send test webhooks with optional HMAC signature validation
        </p>
      </div>

      <form onSubmit={handleSendWebhook} className="space-y-4">
        {/* Event Type */}
        <div className="space-y-2">
          <Label htmlFor="test-event-type">Event Type</Label>
          <Input
            id="test-event-type"
            placeholder="e.g., test.webhook"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="font-mono text-sm"
            required
          />
        </div>

        {/* Webhook Secret (Optional) */}
        <div className="space-y-2">
          <Label htmlFor="webhook-secret">
            Webhook Secret
            <span className="ml-1 text-xs text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="webhook-secret"
            type="password"
            placeholder="Enter webhook secret for HMAC signature"
            value={webhookSecret}
            onChange={(e) => setWebhookSecret(e.target.value)}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            If provided, an HMAC-SHA256 signature will be generated and sent in X-Webhook-Signature header
          </p>
        </div>

        {/* Payload Editor */}
        <div className="space-y-2">
          <Label htmlFor="test-payload">Payload</Label>
          <JsonEditor value={payload} onChange={setPayload} />
        </div>

        {/* Status Messages */}
        {status === "error" && errorMessage && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 flex items-start gap-3">
            <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-destructive text-sm">Error sending webhook</p>
              <p className="text-destructive/80 text-sm mt-1">{errorMessage}</p>
            </div>
          </div>
        )}

        {status === "success" && responseData && (
          <div className="rounded-lg bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 p-4">
            <div className="flex items-start gap-3 mb-2">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium text-green-900 dark:text-green-100 text-sm">Webhook sent successfully</p>
                <p className="text-green-800 dark:text-green-200 text-sm mt-1">Event ID: {responseData.event_id}</p>
              </div>
            </div>
            <pre className="bg-background border rounded p-2 overflow-x-auto text-xs font-mono mt-2">
              {JSON.stringify(responseData, null, 2)}
            </pre>
          </div>
        )}

        {/* Send Button */}
        <Button
          type="submit"
          disabled={status === "sending"}
          className="w-full gap-2"
        >
          {getStatusIcon()}
          {getStatusText()}
        </Button>
      </form>
    </Card>
  )
}
