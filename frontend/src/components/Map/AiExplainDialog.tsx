/**
 * AiExplainDialog
 *
 * Chat dialog that explains the optimizer's plan (or one stop) in plain
 * language. The first explanation loads automatically; the user can then ask
 * follow-up questions. All facts come from the optimizer result sent to the
 * backend; the AI only rephrases them.
 */

import { Loader2, Maximize2, Minus, Send, Sparkles, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import {
  explainFuelOptimization,
  type FuelOptimizationChatMessage,
} from "@/api/fuelOptimization"
import type { FuelOptimizationCalculateResponse } from "@/client"
import { ExplainLanguageSelect } from "@/components/Map/ExplainLanguageSelect"
import { ResizeHandles } from "@/components/Map/ResizeHandles"
import { Markdown } from "@/components/Markdown"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useDraggable } from "@/hooks/useDraggable"
import { useExplainLanguage } from "@/hooks/useExplainLanguage"
import { usePanelStack } from "@/hooks/usePanelStack"
import { useResizable } from "@/hooks/useResizable"

interface AiExplainDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  optimization: FuelOptimizationCalculateResponse
  /** Itinerary sequence of the stop to explain; omit for the whole plan. */
  stopSequence?: number
  stopLabel?: string
  /** Map container to render into, so the panel stays on the map (and in fullscreen). */
  portalContainer?: HTMLElement | null
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
  portalContainer,
}: AiExplainDialogProps) {
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [question, setQuestion] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const requestId = useRef(0)
  const [minimized, setMinimized] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const { zIndex, onPointerDownCapture } = usePanelStack("ai-explain")
  const boundsRef = useRef<HTMLElement | null>(document.documentElement)
  const { dragHandlers, dragStyle, setOffset } = useDraggable(
    panelRef,
    boundsRef,
  )
  const { sizeStyle, startResize, isResizing } = useResizable(panelRef, {
    setOffset,
    boundsRef,
    minWidth: 280,
    minHeight: 180,
  })
  const language = useExplainLanguage()
  const languageRef = useRef(language)
  languageRef.current = language

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
          language: languageRef.current,
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
    // Deferred so React StrictMode's throwaway mount doesn't send a duplicate
    // request (which would burn the provider's token quota).
    const timer = setTimeout(() => void ask(undefined, []), 0)
    return () => {
      clearTimeout(timer)
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

  if (!open) return null

  const title = stopLabel ? `Explain: ${stopLabel}` : "Explain the fuel plan"

  return createPortal(
    <div
      ref={panelRef}
      {...dragHandlers}
      onPointerDown={(event) => {
        dragHandlers.onPointerDown(event)
        event.stopPropagation()
      }}
      onPointerDownCapture={onPointerDownCapture}
      style={{
        ...dragStyle,
        ...(minimized ? {} : sizeStyle),
        zIndex,
        opacity: "var(--floating-opacity, 1)",
      }}
      className={`fixed right-4 flex flex-col rounded-lg border bg-background shadow-lg ${
        minimized
          ? "bottom-4 w-64 cursor-grab"
          : `top-4 bottom-4 ${isResizing ? "select-none" : ""} w-[min(32rem,calc(100vw-2rem))] cursor-grab gap-3 p-4`
      }`}
    >
      {!minimized && <ResizeHandles onResizeStart={startResize} />}
      <div
        className={`flex items-center gap-2 ${minimized ? "px-3 py-2" : ""}`}
      >
        <Sparkles className="h-4 w-4 shrink-0" />
        <h2 className="flex-1 truncate text-sm font-semibold">{title}</h2>
        {isLoading && minimized && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
        <button
          type="button"
          onClick={() => setMinimized((value) => !value)}
          aria-label={minimized ? "Expand" : "Minimize"}
          title={minimized ? "Expand" : "Minimize"}
          className="rounded-md p-1 hover:bg-muted"
        >
          {minimized ? (
            <Maximize2 className="h-4 w-4" />
          ) : (
            <Minus className="h-4 w-4" />
          )}
        </button>
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Close"
          title="Close"
          className="rounded-md p-1 hover:bg-muted"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div
        className={minimized ? "hidden" : "flex min-h-0 flex-1 flex-col gap-3"}
      >
        <p className="text-xs text-muted-foreground">
          Plain-language explanation of the optimizer's decisions. Ask a
          follow-up question below.
        </p>

        <div
          ref={scrollRef}
          data-no-drag
          className="min-h-[8rem] flex-1 cursor-auto space-y-3 overflow-y-auto pr-1 text-sm"
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
              {message.role === "user" ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <Markdown>{message.content}</Markdown>
              )}
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
          className="flex items-center gap-2"
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
          <ExplainLanguageSelect portalContainer={portalContainer} />
          <Button
            type="submit"
            size="icon"
            disabled={isLoading || !question.trim()}
            aria-label="Send"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>,
    portalContainer ?? document.body,
  )
}
