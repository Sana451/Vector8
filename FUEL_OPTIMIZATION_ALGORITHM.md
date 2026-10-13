# Алгоритм оптимизации заправок (Fuel Optimization) — описание, аудит и план рефакторинга

Документ описывает текущую реализацию (`backend/app/fuel_optimization/`), фиксирует её поведение,
а затем перечисляет найденные недостатки, неточности, разночтения и пути рефакторинга.

Разбираемые файлы:

| Файл | Роль |
| --- | --- |
| `domain.py` | Доменные модели + `GreedyFuelOptimizationStrategy` (ядро алгоритма), версия `algorithm_version = "7"` |
| `service.py` | `OptimizeFuelUseCase` — оркестрация, `FuelStationCandidateBuilder`, `ApproximateDetourCalculator`, построение объяснений/таймлайна |
| `repository.py`, `app/map/repository.py` | Выборка маршрута и АЗС вдоль маршрута (PostGIS) |
| `schemas.py` | Публичный API-контракт |

---

## 1. Как алгоритм работает сейчас

### 1.1. Подготовка контекста (`OptimizeFuelUseCase.execute`)

1. Загружаются `Vehicle` + `VehicleFuelProfile` (бак, полезный объём, MPG) и `RouteCalculation`.
2. Геометрия маршрута склеивается из `legs[*].path.coordinates`; требуется ≥ 2 точек.
   `total_distance_meters` берётся **не** из геометрии, а из `route_row.distance_meters` (ответ провайдера).
3. Валидируется резерв (`_validate_reserve`): `min(5, 0.25·usable) ≤ reserve ≤ 0.25·usable`.
   Валидация выполняется **только если резерв передан явно**; иначе резерв = `0`.
4. Строятся кандидаты-АЗС (`FuelStationCandidateBuilder.build`).
5. Собирается `FuelOptimizationContext` и вызывается `FuelOptimizationEngine` → стратегия из реестра.

### 1.2. Отбор станций-кандидатов

Радиус поиска: `max(MAP_LAYER_RADIUS_METERS=5000, max_allowed_detour_meters)`.
Запрос `FuelStationRepository.find_along_route` (PostGIS) возвращает для каждой станции:

* `distance_to_route_meters` = `ST_Distance(location, route::geography)`;
* `progress_along_route` = `ST_LineLocatePoint` (планарная доля 0..1);
* `route_offset_meters` = `ST_Length(ST_LineSubstring(route, 0, fraction)::geography)` — геодезическое смещение.

Детур считается приближённо: `detour_distance = 2 · distance_to_route`,
`detour_time = detour_distance / 13.4112 м/с` (ровно 30 миль/ч).

Фактический порядок фильтров в коде:

1. `route_offset ∉ [0, total_distance]` → `station_outside_route_bounds`;
2. `_outside_route_boundary(...)` (проекция на локальную равнопромежуточную плоскость) → `before_start` / `after_destination`;
3. дубликат `station_id` → `duplicate_station_id`;
4. нормализованный `fuel_type != truck_diesel` → `unsupported_fuel_type`;
5. `diesel_price is None` → `missing_diesel_price`;
6. не `medium_truck_accessible AND large_truck_accessible` → `not_truck_accessible`;
7. `distance_from_route > max_allowed_detour_meters` → `detour_distance_limit_exceeded`;
8. сортировка по `(route_offset, station_id)`.

Каждая станция (принятая или отклонённая) попадает в `audit` и полностью возвращается клиенту
в `explanation.skipped_station_stats`.

### 1.3. Ядро: `GreedyFuelOptimizationStrategy.optimize`

Состояние: `current_offset`, `current_fuel`, `current_station`, аккумуляторы расхода/покупок/детуров.

Расход топлива: `fuel = ((Δoffset + detour_distance) · 0.000621371192237334) / consumption_mpg`
(константная модель `ConstantMpgFuelConsumptionModel`).

Критерий достижимости: `current_fuel − fuel_required ≥ reserve`.

Главный цикл:

```
while True:
    если до финиша хватает топлива с учётом резерва → SUCCESS

    если ещё не были ни на одной АЗС (current_station is None):
        reachable = станции впереди, достижимые с текущим топливом
          (порог прибытия = reserve, но 0, если стартовое топливо уже ниже резерва)
        если пусто → INFEASIBLE (NO_REACHABLE_STATION / DESTINATION_UNREACHABLE)
        выбрать САМУЮ ДЕШЁВУЮ (ties → самую дальнюю), доехать, continue

    # мы стоим на станции
    full_reachable = станции, достижимые ОТ ТЕКУЩЕЙ ТОЧКИ С ПОЛНЫМ БАКОМ
    cheaper_ahead = первая (ближайшая) из них дешевле текущей

    если cheaper_ahead есть:
        desired = ceil4(fuel_to(cheaper_ahead) + reserve)   # «долить ровно до дешёвой»
        next_target = cheaper_ahead
    иначе:
        desired = min(usable, ceil4(fuel_to_destination + reserve))  # «залить под задачу»
        next_target = None

    fuel_added = clamp(desired − current_fuel, 0, usable − current_fuel)
    применить min_refuel_gallons / max_refuel_gallons
    если fuel_added > 0 → записать Stop, прибавить стоимость и детур

    если next_target is None:
        если финиш достижим → continue
        иначе выбрать САМУЮ ДЕШЁВУЮ из достижимых после дозаправки
        если пусто → INFEASIBLE (NO_REACHABLE_CONTINUATION / DESTINATION_UNREACHABLE)

    если current_fuel − fuel_to(next_target) < reserve → INFEASIBLE (PLANNED_STATION_UNREACHABLE)
    доехать до next_target, записать в reached_stations
```

Это классическая жадная схема «задачи о заправках» (Lin et al.): на станции покупать минимум до
первой более дешёвой в радиусе полного бака, иначе заправляться «под завязку»/до цели и идти к
самой дешёвой достижимой. Старт обрабатывается отдельным правилом.

### 1.4. Выход

* `FuelOptimizationPlan` → `stops`, `reached_stations`, агрегаты, `failure`, `debug_trace`.
* `service.py` строит `itinerary` (точки для карты), `explanation` (текст), `algorithm_trace` (таймлайн),
  сохраняет прогон через `FuelOptimizationRunRepository`.
* Каждый шаг `debug_trace` дополнительно пишется в лог через `logger.info`.

---

## 2. Недостатки

### 2.1. Качество оптимизации (алгоритмические)

| # | Проблема | Последствие |
| --- | --- | --- |
| A1 | **Сравнение цен не учитывает детур.** `cheaper_ahead.price < current.price` — голая цена за галлон. Станция дешевле на $0.02, но с детуром 8 км, выбирается как «более дешёвая». | План дороже и дольше реального оптимума. Нужна *эффективная* цена: `price + (детурное топливо · price + время · стоимость_часа) / объём`. |
| A2 | **Нет фиксированной стоимости остановки.** Время заезда/заправки/выезда (обычно 20–40 мин) не моделируется. | Алгоритм охотно плодит много мелких остановок ради копеечной разницы в цене. |
| A3 | **Жадность не оптимальна при детурах.** Классическая жадная схема оптимальна, когда «станция = точка на прямой» без дополнительных затрат. Здесь детур меняет и расход, и позицию — гарантии оптимальности теряются. | Решение субоптимально; нет ни оценки зазора, ни альтернативы (DP). |
| A4 | **Жёсткая ошибка вместо перепланирования.** Если `max_refuel_gallons` не даёт долить до `cheaper_ahead`, алгоритм всё равно едет и возвращает `PLANNED_STATION_UNREACHABLE` вместо выбора ближней станции. То же — если `min_refuel` заставил пропустить заправку. | Ложные «infeasible» при корректных входных данных. |
| A5 | **Нет backtracking.** Первая остановка выбирается по «самой дешёвой достижимой», но дорогая ближняя станция может быть обязательным трамплином к намного более дешёвой дальней. Возврата нет. | Ложные `NO_REACHABLE_CONTINUATION`. |
| A6 | **Нет учёта времени/HOS/окон работы АЗС**, `route.duration_seconds` вообще не используется. | План не исполним в реальной диспетчеризации. |
| A7 | **Нет учёта сетевых/карточных скидок, налогов, IFTA.** Используется сырой `diesel_price`. | Экономика расходится с фактической. |
| A8 | **Константный MPG.** Нет веса груза, уклонов, скорости, погоды. | Систематическая ошибка расхода. |

### 2.2. Корректность и данные

| # | Проблема |
| --- | --- |
| B1 | **`total_distance_meters` (от провайдера, по дорогам) и `route_offset_meters` (геодезическая длина по упрощённой геометрии) — из разных метрик.** Смещения станций систематически не совпадают с общей длиной; ближе к финишу ошибка накапливается. |
| B2 | **Расход на детур списывается всегда, а в `total_detour_distance_meters`/`_time_seconds` детур попадает только если `fuel_added > 0`.** При нулевой дозаправке (станция «проездом») суммарные детуры занижены относительно `total_fuel_consumed_gallons`. |
| B3 | **`LIMIT` без защиты в `find_along_route`.** Для `internal` сортировка `ORDER BY progress_along_route, distance` + `LIMIT 5000`: при превышении лимита молча отбрасывается **хвост маршрута**. С `max_allowed_detour_meters = 100000` (пример из схемы!) радиус 100 км — лимит реально достижим. Итог: ложная инфизибельность на финальном участке без единого предупреждения. |
| B4 | **Тип топлива зашит.** Фильтр — всегда `truck_diesel`, `vehicle.fuel_profile.fuel_type` игнорируется. Провайдер зашит как `"internal"`. |
| B5 | **Свежесть цен не проверяется на уровне алгоритма.** Есть только `expires_at` в SQL: протухший кэш → «станций нет» вместо явной диагностики (хотя `last_imported_at` в модели есть). |
| B6 | **`INITIAL_FUEL_BELOW_RESERVE` недостижим.** Стратегия никогда его не возвращает (ветка в `_build_failure` мертва), но причина опубликована в API и в `types.gen.ts`. Более того, при `initial_fuel < reserve` порог прибытия искусственно опускается до `0` — резерв «молча» нарушается. |
| B7 | **Резерв по умолчанию = 0 и не валидируется.** Если клиент не прислал `constraints`, политика «5 гал / 25 %» полностью обходится. Разночтение между заявленной бизнес-политикой и фактическим поведением. |
| B8 | **Станции с одинаковым `route_offset` теряются.** Условие `station.route_offset_meters <= current_offset` строго отсекает «соседа» с тем же смещением — он становится недостижим навсегда. |
| B9 | **`_fuel_between` использует `max(0, target − current)`** — ошибка порядка станций молча превращается в «0 топлива» вместо исключения. |
| B10 | **Несогласованное округление.** Внутреннее состояние — полная точность, в `Stop` пишутся `_q4`-значения: `fuel_before + fuel_added ≠ fuel_after` на уровне отчёта. Стоимости остановок округляются поштучно (`_money`), а `total_fuel_cost` — от точной суммы: сумма строк ≠ итог. |
| B11 | **`_outside_route_boundary` хрупок.** Равнопромежуточная аппроксимация, направление берётся по *первой отличной* точке геометрии (а не по усреднённому/нормированному вектору), скалярное произведение без нормировки. На извилистых концах маршрута даёт ложные `before_start` / `after_destination`. Плюс дублирует проверку `route_offset ∈ [0, total]`. |

### 2.3. Производительность и эксплуатация

| # | Проблема |
| --- | --- |
| C1 | `_reachable_stations` сканирует **весь** список станций на каждой итерации → O(n²); при n ≈ 5000 и десятках остановок это сотни тысяч `Decimal`-операций. Нужен указатель/бинарный поиск по отсортированным смещениям. |
| C2 | **`debug_trace` строится всегда**, независимо от `include_debug`, и дополнительно каждый шаг логируется `logger.info` (`fuel_optimization_algorithm_step`), плюс по `logger.info` на **каждую** станцию аудита. Это основной источник латентности и объёма логов. |
| C3 | **Безлимитные полезные нагрузки.** `_build_failure` добавляет **все** недостижимые станции впереди; `_build_skipped_station_stats` возвращает **все** отклонённые станции (`omitted_points_count=0` захардкожен). Ответ может весить мегабайты. |
| C4 | `_build_failure` делает ещё один полный проход по `context.stations` с пересчётом топлива. |

### 2.4. Разночтения в коде и документации

| # | Разночтение |
| --- | --- |
| D1 | `debug["formulas"]["route_offset_meters"]` утверждает `progress_fraction · total_distance`, а `audit_entry["formula_route_offset"]` — «геодезическая длина». Код использует геодезическую, доля — лишь fallback. Две формулы в одном ответе противоречат друг другу. |
| D2 | `metadata["filter_sequence"]` **не совпадает** с реальным порядком фильтров и не содержит шагов `station_outside_route_bounds` / boundary-проверки. |
| D3 | Имя `max_allowed_detour_meters` сравнивается с `distance_from_route`, а не с `detour_distance` (= 2×). Фактически это «радиус от маршрута», а не «максимальный детур». В `_reason_description` формулировка ещё и третья. |
| D4 | Одна станция может нарушать несколько правил, но в `audit` попадает только первая сработавшая причина — статистика `excluded_counts` вводит в заблуждение. |
| D5 | Докстринг `_SpatialLayerRepository.find_along_route` и `FuelStationRepository.find_along_route` расходятся по описанию TTL/порядка. |
| D6 | `FuelOptimizationRequest` (dataclass) — мёртвый код, нигде не используется (реальный вход — `FuelOptimizationCalculateRequest`). |
| D7 | `FuelStationCandidate.excursion_distance_meters` — дубликат `distance_from_route_meters`, нигде не читается. |
| D8 | `FuelOptimizationContext.detour_calculator` передаётся в стратегию, но **не используется** (детур считается заранее в билдере). Ложная зависимость. |
| D9 | `FuelOptimizationEngine.optimize(self, request: FuelOptimizationContext)` — параметр назван `request`, а это контекст. |
| D10 | `algorithm_version = "7"` — «магическая» строка без changelog и без связи с содержимым стратегии. |
| D11 | `Detour.is_approximation` всегда `True`, ветки «точного» детура нет — флаг декоративный. |
| D12 | `OptimizeFuelUseCase.execute` ~250 строк: загрузка, валидация, отбор, запуск, логирование, персистентность и презентация в одном методе. |

---

## 3. Что сделано хорошо (сохранить при рефакторинге)

* Чистое разделение домена и инфраструктуры: `Protocol`-интерфейсы (`FuelConsumptionModel`, `DetourCalculator`, `FuelOptimizationStrategy`) + реестр стратегий — расширение на DP/LP не ломает API.
* Все денежные/топливные величины на `Decimal` с явными квантами.
* Очень подробная диагностика: `audit`, `debug_trace`, `failure.primary_target`, `itinerary` с недостижимыми точками — редкая для MVP глубина наблюдаемости.
* Геодезический `route_offset` через `ST_LineSubstring` вместо наивной доли — осознанное решение с комментарием.
* Явное различение `SUCCESS` / `INFEASIBLE` вместо исключений.

---

## 4. Пути рефакторинга

### Шаг 0. Безопасная база (без изменения результатов)

1. Удалить мёртвый код: `FuelOptimizationRequest`, `excursion_distance_meters`, `context.detour_calculator`,
   либо `Detour.is_approximation` реально использовать.
2. Переименовать `FuelOptimizationEngine.optimize(request → context)`.
3. Привести `filter_sequence` и строки формул в соответствие с кодом (D1, D2) — или генерировать их из
   самого конвейера фильтров, чтобы они не могли разойтись.
4. Переименовать `max_allowed_detour_meters` → `max_distance_from_route_meters` (с deprecation-алиасом)
   **или** начать сравнивать его с `detour.distance_meters`. Зафиксировать выбор в схеме и описаниях.

### Шаг 1. Вынести отбор станций в конвейер фильтров

```python
class CandidateFilter(Protocol):
    code: str
    def check(self, row: StationRow, ctx: FilterContext) -> str | None: ...
```

Тогда: порядок фильтров = список объектов (и он же — источник `filter_sequence`),
а станция может накапливать **все** нарушенные правила (устраняет D4).
`FuelStationCandidateBuilder` ужимается до цикла по фильтрам.

### Шаг 2. Разбить `OptimizeFuelUseCase`

* `FuelOptimizationContextAssembler` — загрузка vehicle/route/constraints и валидация.
* `OptimizeFuelUseCase` — только оркестрация (assembler → candidates → engine → repository).
* `FuelOptimizationPresenter` — `itinerary`, `explanation`, `algorithm_trace`, `_serialize_debug`.
  Эти ~400 строк форматирования не место в use case.

### Шаг 3. Телеметрия под флагом

* Ввести `TraceSink` (`NullTraceSink` / `ListTraceSink`), передаваемый в стратегию.
  При `include_debug=False` — никаких словарей и никаких `logger.info` на шаг.
* Пер-станционный аудит-лог заменить одной агрегированной записью (`reason → count`),
  детали — только на `DEBUG`.
* Ввести лимиты и честные `omitted_*_count` для `unreachable_stations` и `skipped_station_stats` (C3).

### Шаг 4. Исправить корректность

1. **B3 (критично):** считать `COUNT(*)` до `LIMIT`; при срезе — вернуть явное предупреждение
   `candidate_search_truncated` и/или перейти к постраничной выборке/прореживанию по маршруту,
   а не молча терять хвост.
2. **B1:** привести `total_distance_meters` и `route_offset` к одной метрике
   (масштабировать смещения коэффициентом `provider_distance / geodesic_length` либо брать
   длину по дорогам из провайдера для каждой точки).
3. **B2:** считать детур при каждом фактическом заезде, а не только при покупке
   (или не заезжать вовсе, если `fuel_added == 0` — тогда и топливо на детур списывать не надо;
   это также снимет вопрос «зачем мы сюда свернули»).
4. **B6/B7:** либо возвращать `INITIAL_FUEL_BELOW_RESERVE` при `initial_fuel < reserve`,
   либо убрать причину из API. Валидацию резерва применять и к значению по умолчанию.
5. **B8:** заменить `<= current_offset` на «исключить уже посещённые `station_id`»
   вместо сравнения смещений.
6. **B9:** в `_fuel_between` бросать исключение при `target < current`.
7. **B10:** квантовать один раз — на границе отчёта, и выводить `total_fuel_cost` как сумму
   уже округлённых `stop.fuel_cost` (или наоборот, но согласованно и с тестом на инвариант).
8. **B11:** заменить ручную геометрию на PostGIS (`ST_LineLocatePoint` + проверка 0 < fraction < 1
   c допуском) либо на нормированный вектор по сглаженному участку геометрии.
9. **B4:** фильтровать по `vehicle.fuel_profile.fuel_type`, провайдера вынести в настройку.

### Шаг 5. Улучшить саму оптимизацию

1. **Эффективная цена** вместо сырой (A1, A2):

   ```
   effective_cost(station, volume) =
       volume * price
     + detour_fuel(station) * price
     + (detour_time + dwell_time) * driver_cost_per_second
     + fixed_stop_cost
   ```

   Сравнение `cheaper_ahead` и выбор «самой дешёвой достижимой» должны идти по этой величине.
2. **Устойчивость к ограничениям (A4):** если `min/max_refuel` не позволяют достичь
   `next_target`, пересчитать цель среди достижимых, а не падать в `INFEASIBLE`.
3. **Точный алгоритм как вторая стратегия (A3, A5):** реестр уже готов — добавить
   `FuelOptimizationAlgorithm.DP` с DP по состояниям `(станция, уровень топлива из сетки)`;
   для n ≤ нескольких сотен кандидатов это секунды. Жадный остаётся быстрым фолбэком,
   а разница в стоимости двух стратегий — отличная регрессионная метрика качества.
4. **Прореживание кандидатов** перед оптимизацией: на каждом «окне» маршрута (например, 50 км)
   оставлять k самых дешёвых по эффективной цене. Это и ускоряет (C1), и снижает риск B3.
5. **Индексный поиск достижимых (C1):** станции отсортированы — искать верхнюю границу
   достижимости `bisect`-ом по смещению, а не полным сканом.
6. **Версионирование (D10):** `algorithm_version` вынести в константу с changelog-комментарием
   и покрыть тестом «версия изменилась ⇒ обновлены золотые сценарии».

### Приоритет

1. B3, B2, B6/B7, B10 — корректность и доверие к цифрам.
2. C2, C3 — латентность и размер ответа (видно пользователю немедленно).
3. Шаги 1–3 (структурный рефакторинг) — чтобы следующие изменения были дешёвыми.
4. A1/A2 (эффективная цена) — наибольший бизнес-эффект на качество плана.
5. A3/A5 (DP-стратегия) — когда нужна доказуемая оптимальность.
