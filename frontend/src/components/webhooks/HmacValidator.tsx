/**
 * HmacValidator Component
 * Utility for generating and validating HMAC-SHA256 signatures
 */

import { useState } from 'react'
import { Card } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Shield, Copy, Check, Info } from 'lucide-react'

export function HmacValidator() {
  const [secret, setSecret] = useState('')
  const [message, setMessage] = useState('')
  const [signature, setSignature] = useState('')
  const [generatedSignature, setGeneratedSignature] = useState('')
  const [validationResult, setValidationResult] = useState<'valid' | 'invalid' | null>(null)
  const [copiedSignature, setCopiedSignature] = useState(false)

  // Generate HMAC-SHA256 signature
  const generateSignature = async () => {
    if (!secret || !message) {
      alert('Please provide both secret and message')
      return
    }

    try {
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

      const signatureBuffer = await crypto.subtle.sign('HMAC', cryptoKey, messageData)
      const hashArray = Array.from(new Uint8Array(signatureBuffer))
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

      setGeneratedSignature(hashHex)
      setValidationResult(null)
    } catch (err) {
      console.error('Failed to generate signature:', err)
      alert('Failed to generate signature')
    }
  }

  // Validate signature
  const validateSignature = async () => {
    if (!secret || !message || !signature) {
      alert('Please provide secret, message, and signature to validate')
      return
    }

    try {
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

      const signatureBuffer = await crypto.subtle.sign('HMAC', cryptoKey, messageData)
      const hashArray = Array.from(new Uint8Array(signatureBuffer))
      const expectedSignature = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

      // Constant-time comparison (as close as we can get in JavaScript)
      const isValid = signature.toLowerCase() === expectedSignature.toLowerCase()
      setValidationResult(isValid ? 'valid' : 'invalid')
      setGeneratedSignature(expectedSignature)
    } catch (err) {
      console.error('Failed to validate signature:', err)
      alert('Failed to validate signature')
    }
  }

  // Copy signature to clipboard
  const copySignature = async () => {
    try {
      await navigator.clipboard.writeText(generatedSignature)
      setCopiedSignature(true)
      setTimeout(() => setCopiedSignature(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  // Clear all fields
  const clearAll = () => {
    setSecret('')
    setMessage('')
    setSignature('')
    setGeneratedSignature('')
    setValidationResult(null)
  }

  return (
    <Card className="p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Shield className="h-4 w-4 text-primary" />
          HMAC Signature Utility
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          Generate and validate HMAC-SHA256 signatures for webhooks
        </p>
      </div>

      <div className="space-y-4">
        {/* Secret Input */}
        <div className="space-y-2">
          <Label htmlFor="hmac-secret">Webhook Secret</Label>
          <Input
            id="hmac-secret"
            type="password"
            placeholder="Enter your webhook secret"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            className="font-mono text-sm"
          />
        </div>

        {/* Message Input */}
        <div className="space-y-2">
          <Label htmlFor="hmac-message">Message (Request Body)</Label>
          <textarea
            id="hmac-message"
            placeholder='{"event_type":"user.created","payload":{"user_id":"123"}}'
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full min-h-[100px] px-3 py-2 text-sm font-mono rounded-md border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
          />
        </div>

        {/* Signature Input (for validation) */}
        <div className="space-y-2">
          <Label htmlFor="hmac-signature">
            Signature to Validate
            <span className="ml-1 text-xs text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="hmac-signature"
            placeholder="Paste signature to validate"
            value={signature}
            onChange={(e) => setSignature(e.target.value)}
            className="font-mono text-sm"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <Button
            type="button"
            onClick={generateSignature}
            className="flex-1"
            variant="default"
          >
            Generate Signature
          </Button>
          {signature && (
            <Button
              type="button"
              onClick={validateSignature}
              className="flex-1"
              variant="outline"
            >
              Validate Signature
            </Button>
          )}
        </div>

        {/* Generated Signature Display */}
        {generatedSignature && (
          <div className="space-y-2">
            <Label>Generated Signature</Label>
            <div className="flex gap-2">
              <Input
                value={generatedSignature}
                readOnly
                className="font-mono text-sm bg-muted"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={copySignature}
                className="shrink-0"
              >
                {copiedSignature ? (
                  <>
                    <Check className="h-3 w-3 mr-1" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3 mr-1" />
                    Copy
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Validation Result */}
        {validationResult && (
          <div className={`rounded-lg border p-4 ${
            validationResult === 'valid'
              ? 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800'
          }`}>
            <p className={`text-sm font-medium ${
              validationResult === 'valid'
                ? 'text-green-900 dark:text-green-100'
                : 'text-red-900 dark:text-red-100'
            }`}>
              {validationResult === 'valid'
                ? '✓ Signature is valid'
                : '✗ Signature is invalid'}
            </p>
          </div>
        )}

        {/* Info Box */}
        <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 p-4">
          <div className="flex items-start gap-2">
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-900 dark:text-blue-100 space-y-1">
              <p className="font-medium">How to use:</p>
              <ol className="list-decimal list-inside space-y-1 ml-2">
                <li>Enter your webhook secret</li>
                <li>Paste the request body (JSON) in the message field</li>
                <li>Click "Generate Signature" to create HMAC-SHA256</li>
                <li>Use the signature in X-Webhook-Signature header</li>
                <li>To validate: paste both message and signature, then click "Validate"</li>
              </ol>
            </div>
          </div>
        </div>

        {/* Clear Button */}
        {(secret || message || signature || generatedSignature) && (
          <Button
            type="button"
            variant="ghost"
            onClick={clearAll}
            className="w-full"
          >
            Clear All
          </Button>
        )}
      </div>
    </Card>
  )
}
