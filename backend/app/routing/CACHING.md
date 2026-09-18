# Документация: Persistent Route Caching с PostgreSQL/PostGIS

## Обзор

Система реализует **cache-first стратегию** для расчёта маршрутов с использованием PostGIS для хранения геопространственных данных.

### Основные характеристики:

- ✅ **Cache-first**: Проверяет БД перед вызовом провайдера
- ✅ **Force refresh**: Query параметр для обновления кэша
- ✅ **PostGIS интеграция**: Хранение геометрии маршрутов
- ✅ **TTL (Time-to-Live)**: Автоматическое истечение кэша
- ✅ **Детерминированное хеширование**: SHA-256 для консистентности
- ✅ **Пространственные индексы**: GiST для оптимизации запросов

---

## Архитектура

### Общий поток обработки:

```
API Request (POST /api/v1/routing/routes/calculate)
    ↓
Router (route handler)
    ↓
RoutingService.calculate_route()
    ├─ Compute request_hash (SHA-256)
    ├─ IF force_refresh=False:
    │   └─ Repository.get_valid_by_provider_and_hash()
    │       ├─ Cache HIT → return cached response
    │       └─ Cache MISS → continue
    ├─ Provider.calculate_route() (TomTom API)
    ├─ Service._persist_calculation()
    │   ├─ Extract coordinates (GeoJSON → WKT)
    │   ├─ Extract geometry (LineString → WKT)
    │   ├─ Extract metrics (distance, duration)
    │   └─ Repository.upsert_by_provider_and_hash()
    │       └─ INSERT or UPDATE route_calculations table
    └─ Return response
    ↓
HTTP Response (CalculateRouteResponse)
```

### Слои архитектуры:

```
┌─────────────────────────────────────────────────┐
│          FastAPI Router Layer                   │
│  (app/routing/router.py)                        │
│  - Query parameter handling                     │
│  - HTTP exception mapping                       │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│        Business Logic Layer                     │
│  (app/routing/service.py: RoutingService)       │
│  - Cache logic (hit/miss/force refresh)         │
│  - Coordinate transformation                    │
│  - Geometry extraction                          │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Persistence Layer                       │
│  (app/routing/repository.py)                    │
│  - CRUD operations                              │
│  - Expiration checks                            │
│  - Upsert logic                                 │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│    Data Layer (SQLModel + PostGIS)              │
│  (app/routing/models.py: RouteCalculation)      │
│  - ORM entity mapping                           │
│  - Geographic column types                      │
│  - Indexes (GiST, standard)                     │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│      PostgreSQL с расширением PostGIS           │
│  - route_calculations table                     │
│  - POINT, LINESTRING geometries (WGS84)         │
│  - JSONB для request/response data              │
└─────────────────────────────────────────────────┘
```

---

## Компоненты системы

### 1. Router (`app/routing/router.py`)

**Файл**: `backend/app/routing/router.py`

```python
@router.post("/routes/calculate", response_model=CalculateRouteResponse)
async def calculate_route(
    request: CalculateRouteRequest,
    routing_service: RoutingServiceDep,
    force_refresh: bool = Query(False, description="Force refresh from provider, skip cache"),
) -> CalculateRouteResponse:
```

**Параметры**:
- `request` (Body): CalculateRouteRequest с координатами и параметрами маршрута
- `force_refresh` (Query): Булев флаг для обхода кэша и обновления у провайдера

**Возвращает**: `CalculateRouteResponse` с одним или несколькими маршрутами

### 2. Service (`app/routing/service.py`)

**Класс**: `RoutingService`

**Методы**:

#### `calculate_route(request, force_refresh=False)`

Основной метод оркестрации расчёта маршрутов.

**Логика**:
1. Вычисляет детерминированный хэш запроса
2. Если `force_refresh=False`: проверяет кэш
3. При попадании в кэш: возвращает сохранённый ответ
4. При промахе или `force_refresh=True`: вызывает провайдера
5. Сохраняет результат в БД
6. Возвращает ответ

```python
async def calculate_route(
    self,
    request: CalculateRouteRequest,
    *,
    force_refresh: bool = False,
) -> CalculateRouteResponse:
```

#### `_persist_calculation(request, response, request_hash, request_data_dict)`

Сохранение расчётного маршрута в БД.

**Операции**:
1. Извлечение координат origin/destination из GeoJSONPoint
2. Преобразование в WKT POINT формат: `SRID=4326;POINT(lon lat)`
3. Извлечение геометрии маршрута (первый leg) в WKT LINESTRING
4. Извлечение метрик (distance_meters, duration_seconds)
5. Сохранение через repository.upsert_by_provider_and_hash()

```python
async def _persist_calculation(
    self,
    request: CalculateRouteRequest,
    response: CalculateRouteResponse,
    request_hash: str,
    request_data_dict: dict,
) -> RouteCalculation:
```

#### `_build_response_from_calculation(calculation)`

Восстановление ответа из кэшированного расчёта.

```python
async def _build_response_from_calculation(
    self,
    calculation: RouteCalculation,
) -> CalculateRouteResponse:
```

### 3. Repository (`app/routing/repository.py`)

**Класс**: `RouteCalculationRepository`

**Методы**:

#### `get_by_provider_and_hash(provider, request_hash)`

Получить любой расчёт по провайдеру и хэшу запроса.

```python
def get_by_provider_and_hash(
    self,
    provider: str,
    request_hash: str,
) -> RouteCalculation | None:
```

#### `get_valid_by_provider_and_hash(provider, request_hash)`

Получить **валидный** (не истёкший) расчёт.

**Проверка**: `datetime.utcnow() < expires_at`

```python
def get_valid_by_provider_and_hash(
    self,
    provider: str,
    request_hash: str,
) -> RouteCalculation | None:
```

#### `upsert_by_provider_and_hash(...)`

Вставить новый или обновить существующий расчёт.

```python
def upsert_by_provider_and_hash(
    self,
    provider: str,
    request_hash: str,
    origin_wkt: str,
    destination_wkt: str,
    distance_meters: int,
    duration_seconds: int,
    request_data: dict,
    provider_response: dict,
    ttl_seconds: int,
    geometry_wkt: str | None = None,
) -> RouteCalculation:
```

**Логика**:
1. Проверяет, существует ли запись с `(provider, request_hash)`
2. Если существует: обновляет все поля (UPDATE)
3. Если нет: создаёт новую запись (INSERT)
4. Вычисляет `expires_at = now + timedelta(seconds=ttl_seconds)`
5. Коммитит в БД

### 4. Hashing (`app/routing/hashing.py`)

**Функция**: `compute_request_hash(request_data)`

Вычисляет детерминированный SHA-256 хэш запроса.

```python
def compute_request_hash(request_data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of routing request."""
    canonical_json = json.dumps(
        request_data,
        sort_keys=True,
        separators=(",", ":"),
    )
    request_hash = hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()
    return request_hash
```

**Особенности**:
- ✅ **Канонический JSON**: Сортированные ключи для консистентности
- ✅ **Компактный формат**: `separators=(",", ":")`  без пробелов
- ✅ **Независимость от порядка**: Разный порядок параметров = один хэш
- ✅ **SHA-256**: 64 символа hex, достаточная безопасность

**Пример**:
```python
# Эти два запроса имеют одинаковый хэш:
request1 = {"a": 1, "b": 2}
request2 = {"b": 2, "a": 1}
# compute_request_hash(request1) == compute_request_hash(request2)
```

---

## База данных

### Таблица: `route_calculations`

**Создание**: Alembic миграция
`4233c86eae69_add_route_calculations_table_with_.py`

### Схема таблицы:

```sql
CREATE TABLE route_calculations (
    -- Первичный ключ
    id VARCHAR NOT NULL PRIMARY KEY,

    -- Уникальные поля для поиска
    provider VARCHAR NOT NULL,                    -- индекс
    request_hash VARCHAR NOT NULL,                -- индекс
    UNIQUE CONSTRAINT uq_route_calc_provider_hash (provider, request_hash),

    -- Географические данные (PostGIS)
    origin GEOGRAPHY(POINT, 4326) NOT NULL,      -- GiST индекс
    destination GEOGRAPHY(POINT, 4326) NOT NULL, -- GiST индекс
    geometry GEOGRAPHY(LINESTRING, 4326),        -- GiST индекс, nullable

    -- Нормализованные метрики
    distance_meters INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL,

    -- Хранилище данных
    request_data JSONB,                           -- исходный запрос
    provider_response JSONB,                      -- ответ провайдера

    -- Временные метки
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,

    CONSTRAINT fk_route_calculations_provider
        FOREIGN KEY (provider) REFERENCES providers(name)
);
```

### Типы данных:

| Столбец | Тип | Назначение |
|---------|-----|-----------|
| `id` | VARCHAR | UUID маршрута |
| `provider` | VARCHAR | Название провайдера (e.g., "tomtom") |
| `request_hash` | VARCHAR | SHA-256 хэш запроса |
| `origin` | GEOGRAPHY(POINT, 4326) | Начальная точка маршрута (WGS84) |
| `destination` | GEOGRAPHY(POINT, 4326) | Конечная точка маршрута (WGS84) |
| `geometry` | GEOGRAPHY(LINESTRING, 4326) | Геометрия пути маршрута |
| `distance_meters` | INTEGER | Расстояние в метрах |
| `duration_seconds` | INTEGER | Время в пути в секундах |
| `request_data` | JSONB | Полный исходный запрос (для отладки) |
| `provider_response` | JSONB | Полный ответ провайдера |
| `created_at` | TIMESTAMP | Когда запись создана |
| `expires_at` | TIMESTAMP | Когда кэш истекает |

### Индексы:

```sql
-- Стандартные индексы для быстрого поиска
CREATE INDEX idx_provider ON route_calculations(provider);
CREATE INDEX idx_request_hash ON route_calculations(request_hash);

-- GiST индексы для пространственных запросов
CREATE INDEX idx_origin_geom ON route_calculations USING GIST(origin);
CREATE INDEX idx_destination_geom ON route_calculations USING GIST(destination);
CREATE INDEX idx_geometry_geom ON route_calculations USING GIST(geometry);

-- Уникальное ограничение (провайдер + хэш = уникальная запись)
CREATE UNIQUE INDEX uq_route_calc_provider_hash
    ON route_calculations(provider, request_hash);
```

### WKT Форматы:

**POINT** (Originдля и destination):
```
SRID=4326;POINT(-87.6298 41.8781)
         ↑       ↑       ↑
       SRID   longitude latitude
```

**LINESTRING** (geometry):
```
SRID=4326;LINESTRING(-87.6298 41.8781, -87.5464 41.7934, -87.3464 41.5934)
         ↑            ↑                  ↑                  ↑
       SRID        point 1              point 2           point 3
```

---

## API Endpoints

### POST `/api/v1/routing/routes/calculate`

Вычисляет маршрут между двумя точками с поддержкой кэширования.

#### Request Headers

```http
Content-Type: application/json
```

#### Request Parameters

**Query Parameters**:
- `force_refresh` (optional, boolean): Игнорировать кэш и обновить у провайдера (default: `false`)

#### Request Body

```json
{
  "route_planning_locations": {
    "origin": {
      "type": "Point",
      "coordinates": [-87.6298, 41.8781]
    },
    "destination": {
      "type": "Point",
      "coordinates": [-87.3464, 41.5934]
    },
    "waypoints": {
      "type": "MultiPoint",
      "coordinates": []
    }
  },
  "route_type": "fast",
  "traffic": "live",
  "travel_mode": "car",
  "departure_date_time": "2026-09-18T10:00:00Z",
  "max_path_alternative_routes": 0
}
```

#### Response (200 OK)

```json
{
  "routes": [
    {
      "summary": {
        "lengthInMeters": 50000,
        "travelDurationInSeconds": 3600,
        "trafficDelayDurationInSeconds": 300
      },
      "legs": [
        {
          "summary": {
            "lengthInMeters": 50000,
            "travelDurationInSeconds": 3600
          },
          "path": {
            "type": "LineString",
            "coordinates": [
              [-87.6298, 41.8781],
              [-87.5464, 41.7934],
              [-87.3464, 41.5934]
            ]
          }
        }
      ]
    }
  ]
}
```

#### Response Codes

| Код | Описание |
|-----|----------|
| 200 | Успешное вычисление маршрута (из кэша или провайдера) |
| 400 | Неверные параметры (e.g., невалидные координаты) |
| 403 | Ошибка аутентификации (неверный API ключ) |
| 429 | Лимит запросов превышен |
| 408 | Timeout запроса |
| 500 | Ошибка провайдера или сервера |
| 503 | Провайдер недоступен |

---

## Примеры использования

### Пример 1: Базовый запрос (с кэшем)

```bash
curl -X POST http://localhost:8000/api/v1/routing/routes/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "route_planning_locations": {
      "origin": {"type": "Point", "coordinates": [-87.6298, 41.8781]},
      "destination": {"type": "Point", "coordinates": [-87.3464, 41.5934]}
    },
    "route_type": "fast",
    "traffic": "live",
    "travel_mode": "car",
    "departure_date_time": "2026-09-18T10:00:00Z"
  }'
```

**Что происходит**:
1. Сервис вычисляет хэш запроса
2. Проверяет БД: есть ли кэширован этот маршрут?
3. Если **кэш попал**: возвращает результат из БД (быстро ✓)
4. Если **кэш промахнулся**: вызывает TomTom API, сохраняет результат, возвращает

### Пример 2: Принудительное обновление кэша

```bash
curl -X POST "http://localhost:8000/api/v1/routing/routes/calculate?force_refresh=true" \
  -H "Content-Type: application/json" \
  -d '{
    "route_planning_locations": {
      "origin": {"type": "Point", "coordinates": [-87.6298, 41.8781]},
      "destination": {"type": "Point", "coordinates": [-87.3464, 41.5934]}
    },
    "route_type": "fast"
  }'
```

**Что происходит**:
1. Игнорирует кэш (даже если кэш есть)
2. Всегда вызывает TomTom API
3. Обновляет или создаёт запись в БД с новыми данными
4. Обновляет `expires_at` на новое время

### Пример 3: Python клиент

```python
import httpx
import asyncio

async def calculate_route():
    async with httpx.AsyncClient() as client:
        # Запрос с кэшем (может быть быстро)
        response1 = await client.post(
            "http://localhost:8000/api/v1/routing/routes/calculate",
            json={
                "route_planning_locations": {
                    "origin": {"type": "Point", "coordinates": [-87.6298, 41.8781]},
                    "destination": {"type": "Point", "coordinates": [-87.3464, 41.5934]},
                },
                "route_type": "fast",
                "traffic": "live",
                "travel_mode": "car",
            }
        )
        print(f"First call: {response1.elapsed.total_seconds():.2f}s")

        # Повторный запрос (будет из кэша)
        response2 = await client.post(
            "http://localhost:8000/api/v1/routing/routes/calculate",
            json={...}  # Одинаковые параметры
        )
        print(f"Cached call: {response2.elapsed.total_seconds():.2f}s")  # Быстрее!

        # Принудительное обновление
        response3 = await client.post(
            "http://localhost:8000/api/v1/routing/routes/calculate?force_refresh=true",
            json={...}
        )
        print(f"Force refresh: {response3.elapsed.total_seconds():.2f}s")

asyncio.run(calculate_route())
```

### Пример 4: Запрос с waypoints

```bash
curl -X POST http://localhost:8000/api/v1/routing/routes/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "route_planning_locations": {
      "origin": {"type": "Point", "coordinates": [-87.6298, 41.8781]},
      "destination": {"type": "Point", "coordinates": [-87.3464, 41.5934]},
      "waypoints": {
        "type": "MultiPoint",
        "coordinates": [
          [-87.5464, 41.7934],
          [-87.4464, 41.6934]
        ]
      }
    },
    "route_type": "short",
    "traffic": "live"
  }'
```

---

## Конфигурация

### Переменные окружения

**Файл**: `backend/app/core/config.py`

```python
class Settings(BaseSettings):
    # ...
    ROUTING_PROVIDER: str = "tomtom"
    ROUTE_CALCULATION_CACHE_TTL_SECONDS: int = 3600  # 1 час
```

### Параметры кэширования

| Параметр | Значение | Описание |
|----------|----------|----------|
| `ROUTING_PROVIDER` | "tomtom" | Используемый провайдер маршрутизации |
| `ROUTE_CALCULATION_CACHE_TTL_SECONDS` | 3600 | Время жизни кэша в секундах (1 час) |

### Как изменить TTL

**Опция 1: Переменная окружения**

```bash
export ROUTE_CALCULATION_CACHE_TTL_SECONDS=7200  # 2 часа
```

**Опция 2: .env файл**

```env
ROUTE_CALCULATION_CACHE_TTL_SECONDS=7200
```

**Опция 3: Код**

```python
from app.core.config import settings
# TTL будет 3600 секунд (1 час) по умолчанию
```

### Рекомендуемые значения TTL

| TTL | Сценарий | Примечание |
|-----|----------|-----------|
| 300s (5 мин) | Быстро меняющиеся маршруты | Часто проверять актуальность |
| 1800s (30 мин) | Среднее время | Баланс между актуальностью и нагрузкой |
| 3600s (1 час) | **DEFAULT** | Рекомендуется для большинства случаев |
| 7200s (2 часа) | Статичные маршруты | Редко меняющиеся пути |
| 86400s (1 день) | Долгосрочное кэширование | Для офлайн сценариев |

---

## Алгоритм кэширования

### Поток принятия решений

```
START: calculate_route(request, force_refresh=?)
    │
    ├─► Compute request_hash(request)
    │
    ├─► IF force_refresh == True
    │   │   → SKIP cache, GO TO PROVIDER
    │   │
    ├─► ELSE (force_refresh == False)
    │   │
    │   └─► Repository.get_valid_by_provider_and_hash()
    │       │
    │       ├─► IF found AND (now < expires_at)
    │       │   │   → CACHE HIT ✓
    │       │   │   → Return cached response
    │       │   │   → END
    │       │   │
    │       └─► ELSE
    │           │   → CACHE MISS ✗
    │           │   → GO TO PROVIDER
    │           │
    ├─► PROVIDER: TomTom API call
    │   │   → Extract distance, duration, geometry
    │   │   → Build CalculateRouteResponse
    │   │
    ├─► PERSIST: _persist_calculation()
    │   │   → Convert coordinates to WKT
    │   │   → Insert/Update route_calculations
    │   │   → Set expires_at = now + TTL
    │   │
    └─► RETURN: response
        │   → HTTP 200 + JSON
        │
END
```

### Кэш-попадание (Cache HIT)

**Условия**:
```
record.expires_at > datetime.utcnow()  AND
(provider, request_hash) совпадают
```

**Действия**:
1. Логируем "cache hit"
2. Десериализуем `provider_response` в `CalculateRouteResponse`
3. Возвращаем без вызова TomTom API
4. **Выигрыш**: Быстрый ответ (из БД вместо API)

### Кэш-промах (Cache MISS)

**Условия**:
```
record.expires_at <= datetime.utcnow()  OR
record не существует
```

**Действия**:
1. Логируем "cache miss"
2. Вызываем TomTom API
3. Получаем свежие данные
4. Сохраняем в БД (INSERT или UPDATE)
5. Возвращаем ответ

### Принудительное обновление (Force Refresh)

**Query параметр**: `?force_refresh=true`

**Действия**:
1. Пропускаем любую проверку кэша
2. Всегда вызываем TomTom API
3. Сохраняем результат (обновляя `expires_at`)
4. Возвращаем новые данные

---

## Миграции и Alembic

### Создание миграции

Миграция автоматически создана Alembic при регистрации `RouteCalculation` модели.

**Файл**: `backend/app/alembic/versions/4233c86eae69_add_route_calculations_table_with_.py`

### Запуск миграций

```bash
# Применить все миграции (вперёд)
alembic upgrade head

# Откатить последнюю миграцию (назад)
alembic downgrade -1

# Просмотреть статус
alembic current

# Создать новую миграцию (если изменили модели)
alembic revision --autogenerate -m "Description"
```

### Структура миграции

```python
def upgrade() -> None:
    # Создание таблицы
    op.create_table('route_calculations', ...)

    # Создание индексов
    op.create_index('idx_provider', 'route_calculations', ['provider'])
    op.create_index('idx_request_hash', 'route_calculations', ['request_hash'])
    op.create_index('idx_origin_geom', ..., postgresql_using='gist')

    # Уникальное ограничение
    op.create_unique_constraint('uq_route_calc_provider_hash', ...)

def downgrade() -> None:
    # Откат
    op.drop_table('route_calculations')
```

---

## Извлечение и трансформация координат

### GeoJSON → WKT преобразование

**Источник**: `CalculateRouteRequest.route_planning_locations.origin/destination`

**Формат GeoJSON**:
```python
origin: GeoJSONPoint = {
    "type": "Point",
    "coordinates": [-87.6298, 41.8781]  # [longitude, latitude]
}
```

**Преобразование в WKT**:
```python
origin_lon, origin_lat = origin.coordinates  # Распаковка кортежа
origin_wkt = f"SRID=4326;POINT({origin_lon} {origin_lat})"
# Результат: "SRID=4326;POINT(-87.6298 41.8781)"
```

### Логика в коде

**Файл**: `backend/app/routing/service.py` → `_persist_calculation()`

```python
# Шаг 1: Получаем GeoJSONPoint объекты
origin = request.route_planning_locations.origin
destination = request.route_planning_locations.destination

# Шаг 2: Распаковываем координаты
origin_lon, origin_lat = origin.coordinates
destination_lon, destination_lat = destination.coordinates

# Шаг 3: Преобразуем в WKT
origin_wkt = f"SRID=4326;POINT({origin_lon} {origin_lat})"
destination_wkt = f"SRID=4326;POINT({destination_lon} {destination_lat})"
```

### Geometry (LineString) из ответа

**Источник**: `CalculateRouteResponse.routes[0].legs[0].path`

**Преобразование**:
```python
if response.routes and len(response.routes) > 0:
    first_route = response.routes[0]
    if first_route.legs and len(first_route.legs) > 0:
        first_leg = first_route.legs[0]
        if first_leg.path:
            coords = first_leg.path.coordinates  # List of (lon, lat) tuples
            coords_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
            geometry_wkt = f"SRID=4326;LINESTRING({coords_str})"
```

**Результат**:
```
SRID=4326;LINESTRING(-87.6298 41.8781, -87.5464 41.7934, -87.3464 41.5934)
```

---

## Обработка ошибок

### Исключения

**Файл**: `backend/app/routing/exceptions.py`

| Исключение | HTTP код | Описание |
|-----------|----------|----------|
| `RoutingBadRequestError` | 400 | Неверные параметры запроса |
| `RoutingAuthenticationError` | 403 | Ошибка аутентификации (API key) |
| `RoutingRateLimitError` | 429 | Превышен лимит запросов |
| `RoutingTimeoutError` | 408 | Timeout при обращении к провайдеру |
| `RoutingProviderError` | 500 | Ошибка провайдера |
| `RoutingUnavailableError` | 503 | Провайдер недоступен |
| `RoutingNoRouteFoundError` | 400 | Маршрут не найден |

### Обработка в Router

**Файл**: `backend/app/routing/router.py`

```python
try:
    return await routing_service.calculate_route(
        request=request,
        force_refresh=force_refresh,
    )
except RoutingError as e:
    status_code = e.status_code or 500
    raise HTTPException(status_code=status_code, detail=e.message) from e
except Exception as e:
    raise HTTPException(status_code=500, detail="Internal server error") from e
```

---

## Логирование

### Структурированное логирование

**Файл**: `backend/app/core/logging.py`

Используется `structlog` для структурированного логирования с контекстом.

### Логируемые события

**В RoutingService**:

```python
logger.info(
    "Route calculation requested",
    origin=request.route_planning_locations.origin.coordinates,
    destination=request.route_planning_locations.destination.coordinates,
    route_type=request.route_type,
    traffic=request.traffic,
)

logger.info(
    "Route calculation cache hit",
    request_hash=request_hash,
    provider=settings.ROUTING_PROVIDER,
)

logger.info(
    "Route calculation cache miss",
    request_hash=request_hash,
    provider=settings.ROUTING_PROVIDER,
)

logger.info(
    "Route calculation force refresh",
    request_hash=request_hash,
    provider=settings.ROUTING_PROVIDER,
)

logger.info(
    "Route calculation persisted",
    calculation_id=calculation.id,
    request_hash=request_hash,
    provider=settings.ROUTING_PROVIDER,
)
```

### Пример логов

```
2026-09-18 12:46:36 [info] Route calculation requested
  origin=(-87.6298, 41.8781)
  destination=(-87.3464, 41.5934)
  route_type=fast
  traffic=live

2026-09-18 12:46:36 [info] Route calculation cache miss
  request_hash=abc123def456...
  provider=tomtom

2026-09-18 12:46:37 [info] Route calculation persisted
  calculation_id=550e8400-e29b-41d4-a716-446655440000
  request_hash=abc123def456...
  provider=tomtom
```

---

## Performance и оптимизация

### Метрики кэша

| Сценарий | Время ответа | Примечание |
|----------|--------------|-----------|
| Cache HIT | ~10-50 ms | Из PostgreSQL |
| Cache MISS | ~500-2000 ms | Вызов TomTom API |
| Force Refresh | ~500-2000 ms | Всегда новый вызов API |

### Оптимизация запросов БД

**1. Индексы**:
```sql
-- Быстрый поиск по провайдеру и хэшу
CREATE INDEX idx_provider ON route_calculations(provider);
CREATE INDEX idx_request_hash ON route_calculations(request_hash);

-- Пространственные запросы
CREATE INDEX idx_origin_geom ON route_calculations USING GIST(origin);
```

**2. JSONB оптимизация**:
- Компактное хранение в `request_data` и `provider_response`
- Индексирование при необходимости (не требуется сейчас)

**3. TTL очистка**:
- Автоматическое удаление истёкших записей можно добавить:
```sql
-- Один раз в день удаляем старые записи
DELETE FROM route_calculations
WHERE expires_at < NOW();
```

### Масштабируемость

**Текущий дизайн**:
- ✅ Горизонтально масштабируемо (несколько инстансов сервиса)
- ✅ PostgreSQL справляется с гигабайтами данных
- ✅ PostGIS индексы оптимизированы для геопространственных запросов

**Будущие улучшения**:
- Redis кэш слой (перед PostgreSQL)
- Асинхронная очистка истёкших записей
- Партиционирование таблицы по датам

---

## Резюме и best practices

### Checklist для использования

- ✅ TTL настроен в зависимости от сценария
- ✅ `force_refresh` используется для обновления
- ✅ Миграции применены (`alembic upgrade head`)
- ✅ Логирование включено для отладки
- ✅ Координаты корректно извлекаются из GeoJSON
- ✅ Geometry корректно преобразуется в WKT

### Best practices

1. **Cache первичен**: Проверяйте кэш ДО вызова API
2. **Детерминированное хеширование**: Используйте `compute_request_hash()`
3. **Пространственные индексы**: Создавайте GiST индексы для геоданных
4. **TTL настройка**: Выбирайте TTL на основе сценария использования
5. **Логирование**: Логируйте cache hit/miss для мониторинга
6. **Error handling**: Ловите `RoutingError` и конвертируйте в HTTP ошибки

---

## Дополнительные ресурсы

- [PostGIS документация](https://postgis.net/docs/)
- [WKT формат](https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry)
- [GeoJSON спецификация](https://geojson.org/)
- [TomTom Routing API](https://developer.tomtom.com/routing-api)
- [SQLModel документация](https://sqlmodel.tiangolo.com/)
- [Alembic миграции](https://alembic.sqlalchemy.org/)

---
