# Vector8 UI Kit — как подключить

## Файлы

- `tokens.css` — все цвета/шрифты как CSS-переменные. Подключается один раз.
- `fonts.css` — импорт Google Fonts (Space Grotesk + IBM Plex Mono).
- `components.css` — классы компонентов (`.btn`, `.input`, `.badge`, `.alert`, `.dtable`, `.tabs` и т.д.).

Порядок импорта важен: `fonts.css` и `tokens.css` — до `components.css`.

## Вариант 1 — обычный CSS (Vite/CRA/любой React-проект без Tailwind)

Скопируй все три файла в `src/styles/` и подключи в корневом файле (`main.jsx` / `index.jsx` / `App.jsx`):

```js
import './styles/fonts.css';
import './styles/tokens.css';
import './styles/components.css';
```

После этого классы работают как обычные CSS-классы в JSX:

```jsx
function ConfirmButton() {
  return <button className="btn md btn-primary">Назначить водителю</button>;
}
```

## Вариант 2 — если во фронтенде уже есть Tailwind

Классы вроде `.btn-primary` не конфликтуют с Tailwind (разные соглашения об именах), но чище будет
перенести цвета токенов в `tailwind.config.js`, чтобы использовать их как `bg-amber-500`,
`text-ink-900` и т.д., а не смешивать два подхода. Если у тебя Tailwind — скажи, и я пересоберу
`tokens.css` в `theme.extend.colors` для конфига, а `components.css` — в готовые Tailwind-классы
через `@apply`.

## Вариант 3 — Django-шаблоны (не React-часть)

Для серверных Django-страниц (не SPA) три файла точно так же кладутся в `static/css/` и
подключаются как обычные `<link rel="stylesheet">` — фреймворк не имеет значения, это чистый CSS
без зависимостей.

## Если нужен отдельный React-компонент, а не просто класс

Для часто используемых вещей (например, кнопки) имеет смысл обернуть класс в компонент один раз,
а не расставлять `className` вручную по всему проекту:

```jsx
// components/Button.jsx
export function Button({ variant = 'primary', size = 'md', children, ...props }) {
  return (
    <button className={`btn ${size} btn-${variant}`} {...props}>
      {children}
    </button>
  );
}

// использование
<Button variant="primary" size="lg">Назначить водителю</Button>
<Button variant="danger" size="sm">Удалить рейс</Button>
```

Такой же подход подойдёт для `Badge`, `Alert`, `StatCard` — обернуть один раз, дальше передавать
только пропсы.

## Логотип

SVG/PNG файлы логотипа (из предыдущего шага) в токены не входят — их нужно класть отдельно,
обычно в `public/` или `src/assets/`, и подключать как обычное изображение или инлайн-SVG
(см. предыдущее сообщение про подключение favicon/apple-touch-icon).
