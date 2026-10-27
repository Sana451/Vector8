import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

const components: Components = {
  h1: ({ node: _node, ...props }) => (
    <h3 className="mt-3 mb-1 text-base font-semibold" {...props} />
  ),
  h2: ({ node: _node, ...props }) => (
    <h3 className="mt-3 mb-1 text-sm font-semibold" {...props} />
  ),
  h3: ({ node: _node, ...props }) => (
    <h4 className="mt-2 mb-1 text-sm font-semibold" {...props} />
  ),
  h4: ({ node: _node, ...props }) => (
    <h4 className="mt-2 mb-1 text-sm font-semibold" {...props} />
  ),
  p: ({ node: _node, ...props }) => <p className="my-2" {...props} />,
  ul: ({ node: _node, ...props }) => (
    <ul className="my-2 list-disc space-y-1 pl-5" {...props} />
  ),
  ol: ({ node: _node, ...props }) => (
    <ol className="my-2 list-decimal space-y-1 pl-5" {...props} />
  ),
  a: ({ node: _node, ...props }) => (
    <a
      className="underline underline-offset-2"
      target="_blank"
      rel="noreferrer"
      {...props}
    />
  ),
  code: ({ node: _node, ...props }) => (
    <code className="rounded bg-background/60 px-1 py-0.5 text-xs" {...props} />
  ),
  pre: ({ node: _node, ...props }) => (
    <pre
      className="my-2 overflow-x-auto rounded bg-background/60 p-2 text-xs"
      {...props}
    />
  ),
  blockquote: ({ node: _node, ...props }) => (
    <blockquote
      className="my-2 border-l-2 border-border pl-3 text-muted-foreground"
      {...props}
    />
  ),
  hr: ({ node: _node, ...props }) => (
    <hr className="my-3 border-border" {...props} />
  ),
  table: ({ node: _node, ...props }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs" {...props} />
    </div>
  ),
  th: ({ node: _node, ...props }) => (
    <th
      className="border border-border bg-background/60 px-2 py-1 text-left font-semibold"
      {...props}
    />
  ),
  td: ({ node: _node, ...props }) => (
    <td className="border border-border px-2 py-1 align-top" {...props} />
  ),
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
