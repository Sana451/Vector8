import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  type ExplainLanguage,
  setExplainLanguage,
  useExplainLanguage,
} from "@/hooks/useExplainLanguage"

export function ExplainLanguageSelect({
  portalContainer,
}: {
  portalContainer?: HTMLElement | null
}) {
  const language = useExplainLanguage()

  return (
    <Select
      value={language}
      onValueChange={(value) => setExplainLanguage(value as ExplainLanguage)}
    >
      <SelectTrigger
        size="sm"
        aria-label="AI explanation language"
        title="AI explanation language"
        className="h-8 w-[72px] gap-1 px-2 text-xs"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent portalContainer={portalContainer}>
        <SelectItem value="en">EN</SelectItem>
        <SelectItem value="ru">RU</SelectItem>
      </SelectContent>
    </Select>
  )
}
