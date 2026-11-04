# Фоновые задачи (Celery)

Документация по подсистеме фоновых и периодических задач: архитектура, режимы запуска, переменные окружения, API, мониторинг, добавление новых задач.

## Содержание

1. [Обзор](#обзор)
2. [Архитектура и структура кода](#архитектура-и-структура-кода)
3. [Задача `fuel.import_pumpprice_mobile`](#задача-fuelimport_pumpprice_mobile)
4. [Режимы запуска](#режимы-запуска)
5. [Переменные окружения](#переменные-окружения)
6. [HTTP API](#http-api)
7. [Мониторинг (Flower)](#мониторинг-flower)
8. [Добавление новой задачи](#добавление-новой-задачи)
9. [Тесты](#тесты)
10. [Диагностика проблем](#диагностика-проблем)

## Обзор

Фоновые задачи выполняются Celery. Брокер сообщений и хранилище результатов — Redis.

| Компонент | Назначение |
| --- | --- |
| `redis` | Брокер (БД `0`) и хранилище результатов (БД `1`). |
| `worker` | Выполняет задачи из очереди. Можно запускать несколько. |
| `beat` | Кладёт периодические задачи в очередь по расписанию. Строго **один** экземпляр. |
| `flower` | Веб-интерфейс мониторинга задач и воркеров. |
| `backend` (FastAPI) | Ставит задачи в очередь вручную (`.delay()`) и отдаёт их статус. |

Первая задача — периодическое обновление цен на топливо через мобильное API PumpPrice. Логика та же, что у синхронного эндпоинта `POST /fuel/import/pumpprice/mobile`: вызывается `PumpPriceImportService.import_prices_mobile()`.

Схема работы:

1. `beat` по cron кладёт задачу в Redis (если `PUMPPRICE_MOBILE_SYNC_ENABLED=true`).
2. `worker` забирает задачу и берёт advisory-lock в PostgreSQL, чтобы запуски не пересекались.
3. Вызывается сервис импорта, станции записываются в таблицу кэша топливных станций.
4. Результат (счётчики или причина пропуска) сохраняется в Redis на `CELERY_RESULT_EXPIRES_SECONDS`.
5. Результат виден во Flower и через `GET /fuel/import/pumpprice/mobile/tasks/{task_id}`.

## Архитектура и структура кода

```
backend/app/
├── tasks/
│   ├── celery_app.py   # экземпляр Celery, общие настройки, TASK_MODULES
│   ├── schedule.py     # реестр периодических задач (beat_schedule)
│   ├── base.py         # VectorTask (логирование) и advisory_lock
│   └── runner.py       # run_async(): вызов async-кода из синхронных задач
├── fuel/
│   ├── tasks.py        # задача fuel.import_pumpprice_mobile
│   ├── router.py       # эндпоинты запуска и статуса
│   └── schemas.py      # ImportTaskEnqueuedResponse, ImportTaskStatusResponse
└── core/config.py      # настройки CELERY_* и PUMPPRICE_MOBILE_SYNC_*
```

Ключевые решения:

* **Общие настройки Celery** (`celery_app.py`): сериализация JSON; `task_acks_late` и `task_reject_on_worker_lost` (задача не теряется при падении воркера); `worker_prefetch_multiplier=1` (долгие задачи не копятся в префетче); `task_track_started`; жёсткий лимит времени `CELERY_TASK_TIME_LIMIT_SECONDS`, мягкий — на 60 секунд меньше.
* **Реестр расписаний** (`schedule.py`): функция `build_beat_schedule()` включает в расписание только разрешённые настройками задачи.
* **Защита от параллельного запуска** (`base.py`): `advisory_lock(name)` берёт `pg_try_advisory_lock` на отдельном соединении PostgreSQL с `AUTOCOMMIT`. Ключ — `crc32(имя задачи)`. Если блокировка занята, задача завершается со статусом `skipped`. Блокировка защищает от пересечения расписания, ручного запуска и нескольких воркеров.
* **Async в Celery** (`runner.py`): задачи синхронные, async-сервисы вызываются через `asyncio.run`. Токен мобильного API (`_mobile_api_key` в `fuel/service.py`) хранится в глобальной переменной модуля, поэтому у каждого процесса воркера он свой.
* **Логирование**: `VectorTask` пишет события успеха, повтора и ошибки через structlog. Формат (`ConsoleRenderer` или JSON) выбирается по `FASTAPI_ENV`.

## Задача `fuel.import_pumpprice_mobile`

Имя задачи: `fuel.import_pumpprice_mobile` (константа `PUMPPRICE_MOBILE_IMPORT_TASK` в `app/tasks/schedule.py`).

Порядок выполнения:

1. Если не заданы `PUMPPRICE_MOBILE_EMAIL` или `PUMPPRICE_MOBILE_PASSWORD`, задача возвращает `{"status": "skipped", "reason": "credentials_not_configured"}`.
2. Берётся advisory-lock. Если он занят: `{"status": "skipped", "reason": "already_running"}`.
3. Открывается сессия БД, вызывается `import_prices_mobile()`.
4. Возвращается `{"status": "ok", ...}` со счётчиками.

Пример результата:

```json
{
  "status": "ok",
  "source_provider": "pumpprice-mobile",
  "persisted_provider": "internal",
  "stations_received": 1280,
  "unique_stations": 1280,
  "duplicates_discarded": 0,
  "persisted_stations": 1280
}
```

Повторы при ошибках:

| Исключение | Поведение |
| --- | --- |
| `ProviderAuthenticationError` | Не повторяется (ошибка логина или пароля). Задача завершается как `FAILURE`. |
| Любой другой `ProviderError` | До 3 повторов, экспоненциальный backoff (максимум 600 с) с jitter. |
| Прочие исключения | Без повторов, статус `FAILURE`. |

Токен мобильного API при ответе `401` обновляется автоматически (логика в `PumpPriceImportService`).

Срок жизни записей: поле `ttl_seconds` для станций берётся из `FUEL_CACHE_TTL_SECONDS` (по умолчанию 86400 с). При часовом расписании это значение больше интервала, поэтому записи не успевают устареть между запусками.

## Режимы запуска

### Режим 1. Локальная разработка: процессы на хосте

`fastapi dev` и Celery запускаются как обычные процессы, Postgres и Redis в Docker. Подходит для отладки кода.

```bash
docker compose up -d db redis
cd backend
uv sync
uv run bash scripts/prestart.sh

# Каждый процесс в своём терминале
uv run fastapi dev
uv run celery -A app.tasks.celery_app worker -l info
uv run celery -A app.tasks.celery_app beat -l info          # только если включено расписание
uv run celery -A app.tasks.celery_app flower --port=5555    # опционально
```

* Настройки читаются из `.env` в корне репозитория.
* Адреса Redis по умолчанию (`redis://localhost:6379/0` и `/1`) подходят, порт `6379` публикует `compose.override.yml`.
* Flower: <http://localhost:5555>. Без `FLOWER_BASIC_AUTH` доступ открытый (локально это приемлемо).
* Без `redis` и `worker` эндпоинт `POST .../async` вернёт ошибку, так как брокер недоступен. Синхронный эндпоинт продолжит работать.

### Режим 2. Локальный полный стек в Docker Compose

```bash
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

Загружаются `compose.yml` и `compose.override.yml`. Поднимаются `redis`, `worker`, `beat`, `flower` вместе с остальными сервисами.

* У `worker`, `beat` и `flower` та же сборка, что у `backend` (общий YAML-якорь `&backend-build`). После изменения зависимостей или кода образ пересобирается командой `docker compose build` или автоматически при `watch`.
* Адреса брокера в контейнерах жёстко заданы: `redis://redis:6379/0` и `redis://redis:6379/1`. Значения из `.env` для этих двух переменных внутри контейнеров не используются.
* `compose.override.yml` задаёт `FASTAPI_ENV=development` для `worker`, `beat`, `flower`. Без этого приложение отвергает значение `changethis` для `SECRET_KEY`.
* Flower: <http://localhost:5555> и `http://flower.localhost` через Traefik. Логин и пароль из `FLOWER_BASIC_AUTH`, по умолчанию `admin:admin`.
* Запускать только Celery-сервисы: `docker compose up -d redis worker beat flower`.

### Режим 3. Продакшен на своём сервере: Docker Compose

```bash
docker compose -f compose.yml -f compose.deploy.yml build
docker compose -f compose.yml -f compose.deploy.yml run --rm backend bash scripts/prestart.sh
docker compose -f compose.yml -f compose.deploy.yml up -d
```

Загружаются `compose.yml` и `compose.deploy.yml` (без override).

* Для `redis`, `worker`, `beat`, `flower` включён `restart: always`.
* Flower доступен по HTTPS: `https://flower.${DOMAIN}` (сертификат Let's Encrypt через Traefik).
* **`FLOWER_BASIC_AUTH` обязательна**. Без неё Compose не запустится. Задайте надёжный пароль в формате `user:password`.
* `FASTAPI_ENV` не задаётся: значения `changethis` для секретов недопустимы, приложение откажется стартовать.
* Расписание включается переменной `PUMPPRICE_MOBILE_SYNC_ENABLED=true`. В `compose.yml` у неё по умолчанию `false`. Для деплоя через GitHub Actions значение нужно передавать в окружение (репозиторные переменные и секреты).
* Масштабирование воркеров: `docker compose ... up -d --scale worker=3`. Экземпляр `beat` всегда один.
* Расписание (`crontab`) хранится в коде и состояния не требует, поэтому файл `/tmp/celerybeat-schedule` в контейнере можно терять.

### Режим 4. FastAPI Cloud

FastAPI Cloud запускает только веб-приложение (см. [deployment.md](./deployment.md)). `worker`, `beat` и Flower там не работают, поэтому расписание само не сработает.

Варианты:

* **Внешний Redis + отдельный хост.** Создайте Redis (Upstash, Redis Cloud и т. д.). Укажите `CELERY_BROKER_URL` и `CELERY_RESULT_BACKEND` как секреты в FastAPI Cloud. На отдельной машине запустите сервисы `worker`, `beat`, `flower` из `compose.yml` с тем же `DATABASE_URL` и теми же адресами Redis.
* **Без фоновых задач.** Пользоваться синхронным эндпоинтом `POST /fuel/import/pumpprice/mobile`, а расписание не включать.

Для варианта с внешним Redis учтите: в `compose.yml` адреса брокера заданы как `redis://redis:6379/...`. Для подключения к внешнему Redis измените их в окружении `worker`, `beat`, `flower` или запускайте процессы командами из режима 1 с нужными переменными.

### Режим 5. Тесты (eager)

`CELERY_TASK_ALWAYS_EAGER=true` выполняет задачи синхронно в процессе вызова, без брокера и воркера. Результаты при этом не отправляются в Redis. Advisory-lock по-прежнему использует PostgreSQL, поэтому БД всё равно нужна. Тесты проекта вызывают `task.run()` напрямую или подменяют `delay` и `AsyncResult`, поэтому Redis не требуется.

## Переменные окружения

### Celery и брокер

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | URL брокера. В Compose внутри контейнеров всегда `redis://redis:6379/0`. |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | URL хранилища результатов. В Compose — `redis://redis:6379/1`. |
| `CELERY_TIMEZONE` | `UTC` | Часовой пояс для cron-расписания. Значение в формате IANA, например `America/Chicago`. |
| `CELERY_TASK_TIME_LIMIT_SECONDS` | `1800` | Жёсткий лимит выполнения задачи. Мягкий лимит равен этому значению минус 60 с. Значение не меньше 61. |
| `CELERY_RESULT_EXPIRES_SECONDS` | `86400` | Время хранения результатов задач в Redis. |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | Выполнять задачи синхронно, без брокера (для тестов). |
| `CELERY_WORKER_CONCURRENCY` | `2` | Число процессов воркера. Читается **только в Compose** (`--concurrency`). |

> `CELERY_TASK_TIME_LIMIT_SECONDS`, `CELERY_RESULT_EXPIRES_SECONDS` и `CELERY_TASK_ALWAYS_EAGER` не прокидываются в контейнеры в `compose.yml`, там действуют значения по умолчанию. Чтобы изменить их в Docker, добавьте переменные в блок `environment` (`&task-env`) в `compose.yml`.

### Расписание PumpPrice

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `PUMPPRICE_MOBILE_SYNC_ENABLED` | `false` | Включает периодическую задачу в `beat`. Изменение требует перезапуска `beat`. |
| `PUMPPRICE_MOBILE_SYNC_CRON_MINUTE` | `0` | Поле minute в crontab. |
| `PUMPPRICE_MOBILE_SYNC_CRON_HOUR` | `*` | Поле hour в crontab. |

Значения по умолчанию дают запуск каждый час в начале часа (`0 * * * *`). Примеры:

| Расписание | MINUTE | HOUR |
| --- | --- | --- |
| Каждый час | `0` | `*` |
| Каждые 30 минут | `*/30` | `*` |
| Каждые 6 часов | `0` | `*/6` |
| Ежедневно в 03:00 | `0` | `3` |
| В 06:00 и 18:00 | `0` | `6,18` |

Время трактуется в `CELERY_TIMEZONE`.

### Доступ к PumpPrice (используются задачей)

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `PUMPPRICE_MOBILE_EMAIL` | — | Логин мобильного приложения. Без него задача пропускается. |
| `PUMPPRICE_MOBILE_PASSWORD` | — | Пароль. Хранить как секрет. |
| `PUMPPRICE_BASE_URL` | `https://www.pumpprice.co` | Базовый URL API. |
| `PUMPPRICE_TIMEOUT_SECONDS` | `30` | Таймаут HTTP-запросов к PumpPrice. |
| `FUEL_CACHE_TTL_SECONDS` | `86400` | TTL записей станций, выставляемый при импорте. |

### Flower

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `FLOWER_BASIC_AUTH` | `admin:admin` в `compose.yml`, обязательна в `compose.deploy.yml` | Логин и пароль Flower в формате `user:password`. |

### Общие переменные, влияющие на задачи

| Переменная | Описание |
| --- | --- |
| `DATABASE_URL` | Подключение к PostgreSQL. В Compose задаётся автоматически из `POSTGRES_PASSWORD`. |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL (обязателен для Compose). |
| `FASTAPI_ENV` | `development` разрешает значения `changethis` для секретов и включает цветной лог. Без него — JSON-лог. |
| `PROJECT_NAME`, `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD` | Обязательные настройки приложения. Воркеру они нужны, потому что он импортирует `app.core.config`. |
| `SENTRY_DSN` | DSN Sentry. В Compose передаётся воркеру. |
| `DOMAIN` | Домен для маршрутизации Traefik (`flower.${DOMAIN}`). |

## HTTP API

Все эндпоинты доступны только суперпользователю и расположены под `/api/v1/fuel`.

| Метод и путь | Описание |
| --- | --- |
| `POST /import/pumpprice/mobile` | Старый синхронный импорт (блокирует запрос). |
| `POST /import/pumpprice/mobile/async` | Ставит задачу в очередь. Ответ `202`: `{"task_id": "...", "task_name": "fuel.import_pumpprice_mobile"}`. Если брокер недоступен, ответ `503`. |
| `GET /import/pumpprice/mobile/tasks/{task_id}` | Состояние задачи. |

Ответ статуса:

```json
{
  "task_id": "abc-123",
  "state": "SUCCESS",
  "result": {"status": "ok", "persisted_stations": 1280},
  "error": null
}
```

Состояния: `PENDING` (в очереди или неизвестный id), `STARTED`, `RETRY`, `SUCCESS`, `FAILURE`. При `FAILURE` в `error` приходит текст исключения. Если задача была пропущена (нет логина или занят lock), состояние `SUCCESS`, а в `result.status` — `skipped` с полем `reason`.

Пример:

```bash
TOKEN=...   # токен суперпользователя
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/fuel/import/pumpprice/mobile/async
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/fuel/import/pumpprice/mobile/tasks/<task_id>
```

## Мониторинг (Flower)

Flower показывает воркеры, активные и завершённые задачи, их аргументы, результаты, время и ошибки. Адреса:

* локально: <http://localhost:5555>;
* продакшен: `https://flower.<DOMAIN>`.

Для проверки без Flower:

```bash
docker compose logs -f worker
docker compose logs -f beat
```

Запуск задачи вручную из контейнера:

```bash
docker compose exec worker python -c "
from app.fuel.tasks import import_pumpprice_mobile as t
print(t.delay().get(timeout=60))"
```

## Добавление новой задачи

1. Создайте модуль с задачей, например `backend/app/<домен>/tasks.py`:

   ```python
   from app.tasks.base import VectorTask, advisory_lock
   from app.tasks.celery_app import celery_app

   @celery_app.task(name="domain.my_task", base=VectorTask)
   def my_task() -> dict:
       with advisory_lock("domain.my_task") as acquired:
           if not acquired:
               return {"status": "skipped", "reason": "already_running"}
           ...
       return {"status": "ok"}
   ```

2. Добавьте модуль в `TASK_MODULES` в `backend/app/tasks/celery_app.py`.
3. Для периодического запуска добавьте запись в `build_beat_schedule()` в `backend/app/tasks/schedule.py` и при необходимости новые настройки в `core/config.py`.
4. Если задача вызывает async-код, используйте `run_async(...)` из `app.tasks.runner`.
5. Результат задачи должен быть JSON-сериализуемым (используйте `model_dump(mode="json")`).
6. Новые переменные окружения прокиньте в `&task-env` в `compose.yml` и добавьте в `.env.example`.
7. Добавьте тесты в `backend/tests/tasks/`.

## Тесты

```bash
docker compose up -d db
cd backend
uv run pytest tests/tasks tests/fuel -q
```

Тесты проверяют реестр расписания, регистрацию задачи, пропуск без логина и при занятом lock, а также эндпоинты запуска и статуса. Для тестов нужна доступная БД PostgreSQL, Redis не нужен.

## Диагностика проблем

| Симптом | Причина и решение |
| --- | --- |
| `executable file not found: celery` или `NO_CELERY_IN_IMAGE` | Образ `backend:latest` собран до добавления Celery. Выполните `docker compose build`. |
| Воркер падает с `The value of SECRET_KEY is "changethis"` | Не задан `FASTAPI_ENV=development` (локально). В продакшене задайте настоящие секреты. |
| `POST .../async` возвращает `503` | Брокер (Redis) недоступен. Проверьте `docker compose ps redis` и `CELERY_BROKER_URL`. |
| Задача остаётся в `PENDING` | Воркер не запущен или не подключён к тому же Redis. Также `PENDING` возвращается для неизвестных `task_id`. |
| Результат `skipped / credentials_not_configured` | Не заданы `PUMPPRICE_MOBILE_EMAIL` и `PUMPPRICE_MOBILE_PASSWORD`. |
| Результат `skipped / already_running` | Предыдущий запуск ещё идёт (lock занят). Это нормальное поведение. |
| Расписание не срабатывает | `PUMPPRICE_MOBILE_SYNC_ENABLED=false` или `beat` не перезапущен после изменения. Проверка: `docker compose exec beat python -c "from app.tasks.celery_app import celery_app as a; print(a.conf.beat_schedule)"`. |
| Задача выполняется дважды в час | Запущено более одного экземпляра `beat`. Оставьте один. |
| Статус `FAILURE`, `ProviderAuthenticationError` | Неверные учётные данные PumpPrice. Повторов нет, задача упала сразу. |
| Docker Compose требует `FLOWER_BASIC_AUTH` | Нужна только при деплое с `compose.deploy.yml`. Задайте `user:password`. |
