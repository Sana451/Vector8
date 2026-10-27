/**
 * AiExplainDialog
 *
 * Chat dialog that explains the optimizer's plan (or one stop) in plain
 * language. The first explanation loads automatically; the user can then ask
 * follow-up questions. All facts come from the optimizer result sent to the
 * backend; the AI only rephrases them.
 */

import { Loader2, Send, Sparkles } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import {
  explainFuelOptimization,
  type FuelOptimizationChatMessage,
} from "@/api/fuelOptimization"
import type { FuelOptimizationCalculateResponse } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

interface AiExplainDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  optimization: FuelOptimizationCalculateResponse
  /** Itinerary sequence of the stop to explain; omit for the whole plan. */
  stopSequence?: number
  stopLabel?: string
}

interface ChatEntry extends FuelOptimizationChatMessage {
  source?: "ai" | "fallback"
}

const MAX_QUESTION_LENGTH = 1000

export function AiExplainDialog({
  open,
  onOpenChange,
  optimization,
  stopSequence,
  stopLabel,
}: AiExplainDialogProps) {
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [question, setQuestion] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const requestId = useRef(0)

  const ask = useCallback(
    async (text: string | undefined, history: ChatEntry[]) => {
      const currentRequest = ++requestId.current
      setIsLoading(true)
      setError(null)
      try {
        const response = await explainFuelOptimization({
          optimization,
          stop_sequence: stopSequence ?? null,
          question: text ?? null,
          history: history.map(({ role, content }) => ({ role, content })),
          language: navigator.language.slice(0, 2) || "en",
        })
        if (currentRequest !== requestId.current) return
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: response.answer,
            source: response.source,
          },
        ])
      } catch {
        if (currentRequest !== requestId.current) return
        setError("Could not get an explanation. Please try again.")
      } finally {
        if (currentRequest === requestId.current) setIsLoading(false)
      }
    },
    [optimization, stopSequence],
  )

  useEffect(() => {
    if (!open) return
    setMessages([])
    setQuestion("")
    void ask(undefined, [])
    return () => {
      requestId.current++
    }
  }, [open, ask])

  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll on new content
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, isLoading])

  const submit = () => {
    const text = question.trim()
    if (!text || isLoading) return
    const history = messages
    setMessages([...history, { role: "user", content: text }])
    setQuestion("")
    void ask(text, [...history])
  }

  const retry = () => {
    const last = [...messages].reverse().find((m) => m.role === "user")
    const history = last ? messages.slice(0, messages.lastIndexOf(last)) : []
    void ask(last?.content, history)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[85vh] flex-col gap-3 sm:max-w-lg"
        onPointerDown={(event) => event.stopPropagation()}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            {stopLabel ? `Explain: ${stopLabel}` : "Explain the fuel plan"}
          </DialogTitle>
          <DialogDescription>
            Plain-language explanation of the optimizer's decisions. Ask a
            follow-up question below.
          </DialogDescription>
        </DialogHeader>

        <div
          ref={scrollRef}
          className="min-h-[8rem] flex-1 space-y-3 overflow-y-auto pr-1 text-sm"
        >
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={
                message.role === "user"
                  ? "ml-8 rounded-lg bg-primary px-3 py-2 text-primary-foreground"
                  : "mr-8 rounded-lg bg-muted px-3 py-2"
              }
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.source === "fallback" && (
                <p className="mt-2 text-xs text-muted-foreground">
                  AI is unavailable right now; showing the optimizer's built-in
                  explanation.
                </p>
              )}
            </div>
          ))}
          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Thinking…
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              {error}
              <Button size="sm" variant="outline" onClick={retry}>
                Retry
              </Button>
            </div>
          )}
        </div>

        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <Input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={MAX_QUESTION_LENGTH}
            placeholder="Ask a follow-up, e.g. why not the cheaper station?"
            aria-label="Follow-up question"
          />
          <Button
            type="submit"
            size="icon"
            disabled={isLoading || !question.trim()}
            aria-label="Send"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
