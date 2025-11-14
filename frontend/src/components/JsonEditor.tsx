import { useState, useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

interface JsonEditorProps {
  value: string
  onChange: (value: string) => void
  className?: string
}

export function JsonEditor({ value, onChange, className }: JsonEditorProps) {
  const [isValid, setIsValid] = useState(true)
  const [lineNumbers, setLineNumbers] = useState<number[]>([])
  const [textareaHeight, setTextareaHeight] = useState<number>(240)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const lineNumbersRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const lines = value.split("\n").length
    setLineNumbers(Array.from({ length: lines }, (_, i) => i + 1))

    // Auto-adjust height based on number of lines
    // Each line is approximately 24px (leading-6 = 1.5 * 16px)
    const calculatedHeight = Math.max(240, Math.min(600, lines * 24 + 24))
    setTextareaHeight(calculatedHeight)
  }, [value])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value
    onChange(newValue)

    try {
      JSON.parse(newValue)
      setIsValid(true)
    } catch {
      setIsValid(false)
    }
  }

  // Sync scroll between textarea and line numbers
  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (lineNumbersRef.current && textareaRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop
    }
  }

  return (
    <div className={cn("relative rounded-lg border border-input overflow-hidden", className)}>
      <div className="flex relative" style={{ height: `${textareaHeight}px`, minHeight: '240px', maxHeight: '600px' }}>
        {/* Line numbers */}
        <div
          ref={lineNumbersRef}
          className="bg-muted/50 px-3 py-3 select-none shrink-0 border-r border-border w-[50px] overflow-hidden"
          style={{ height: '100%' }}
        >
          {lineNumbers.map((num) => (
            <div key={num} className="font-mono text-xs text-muted-foreground leading-6 text-right">
              {num}
            </div>
          ))}
        </div>

        {/* Editor */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onScroll={handleScroll}
            className={cn(
              "w-full h-full p-3 bg-secondary/30 font-mono text-sm leading-6 resize-none outline-none",
              "text-foreground placeholder:text-muted-foreground",
              !isValid && "text-destructive",
            )}
            spellCheck={false}
            placeholder={'{\n  "key": "value"\n}'}
            style={{
              boxSizing: 'border-box',
            }}
          />

          {/* Validation indicator */}
          <div className="absolute top-2 right-2 z-10 pointer-events-none">
            {isValid ? (
              <div className="px-2 py-1 rounded bg-success/20 text-success text-xs font-mono border border-success/30">
                Valid JSON
              </div>
            ) : (
              <div className="px-2 py-1 rounded bg-destructive/20 text-destructive text-xs font-mono border border-destructive/30">
                Invalid JSON
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
