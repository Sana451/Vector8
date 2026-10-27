import type { ReactNode } from "react"

const INLINE_PATTERN = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE_PATTERN).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code
          key={index}
          className="rounded bg-background/60 px-1 py-0.5 text-xs"
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={index}>{part.slice(1, -1)}</em>
    }
    return part
  })
}

const HEADING_PATTERN = /^(#{1,6})\s+(.*)$/
const BULLET_PATTERN = /^\s*[-*•]\s+(.*)$/
const NUMBERED_PATTERN = /^\s*\d+[.)]\s+(.*)$/

export function MarkdownText({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n")
  const blocks: ReactNode[] = []
  let listItems: ReactNode[] = []
  let listOrdered = false

  const flushList = () => {
    if (listItems.length === 0) return
    const items = listItems
    blocks.push(
      listOrdered ? (
        <ol
          key={`list-${blocks.length}`}
          className="ml-5 list-decimal space-y-1"
        >
          {items}
        </ol>
      ) : (
        <ul key={`list-${blocks.length}`} className="ml-5 list-disc space-y-1">
          {items}
        </ul>
      ),
    )
    listItems = []
  }

  lines.forEach((line, index) => {
    const heading = line.match(HEADING_PATTERN)
    const bullet = line.match(BULLET_PATTERN)
    const numbered = line.match(NUMBERED_PATTERN)

    if (bullet || numbered) {
      const ordered = !bullet
      if (listItems.length > 0 && listOrdered !== ordered) flushList()
      listOrdered = ordered
      listItems.push(
        <li key={`item-${index}`}>
          {renderInline((bullet ?? numbered)?.[1] ?? "")}
        </li>,
      )
      return
    }

    flushList()

    if (heading) {
      blocks.push(
        <p key={`h-${index}`} className="font-semibold">
          {renderInline(heading[2])}
        </p>,
      )
    } else if (line.trim() === "") {
      return
    } else {
      blocks.push(<p key={`p-${index}`}>{renderInline(line)}</p>)
    }
  })
  flushList()

  return <div className="space-y-2">{blocks}</div>
}
