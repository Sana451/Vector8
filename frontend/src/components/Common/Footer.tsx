import { FaGithub } from "react-icons/fa"

const links = [
  {
    icon: FaGithub,
    href: "https://github.com/Sana451/Vector8",
    label: "GitHub",
  },
]

export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t border-border/80 px-6 py-5">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-semibold tracking-tight">
            Vector8 · {currentYear}
          </p>
          <p className="text-muted-foreground text-sm">
            Mapping, routing and operations workspace for modern fleet teams.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {links.map(({ icon: Icon, href, label }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              className="inline-flex items-center gap-2 rounded-md border border-border/80 bg-card px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </a>
          ))}
        </div>
      </div>
    </footer>
  )
}
