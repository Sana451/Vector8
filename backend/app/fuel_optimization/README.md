# Fuel Optimization MVP

## Что добавлено

- `POST /api/v1/fuel-optimization/calculate`
- `CRUD /api/v1/vehicles`
- persisted `route_id` в `POST /api/v1/routing/routes/calculate`
- таблицы:
  - `vehicle_fuel_profiles`
  - `vehicles`
  - `fuel_optimization_runs`
  - `fuel_optimization_stops`

## Алгоритм

Текущий MVP использует `greedy` стратегию:

- если впереди в пределах полного бака есть более дешёвая станция — покупаем только до неё + reserve
- иначе заправляемся до максимально полезного уровня и едем как можно дальше
- detour считается приближённо как `2 * distance_from_route`

## Ограничения MVP

- доступ к vehicle/fuel-optimization API ограничен superuser-ролями
- оптимизация работает по уже сохранённому `route_id`
- выбираются только internal-станции с truck diesel и truck accessibility
- detour-time является приближением

## Расширение

Следующие шаги:

- ownership вместо superuser-only доступа
- отдельные routing profiles и vehicle-specific accessibility rules
- более точный detour provider/graph service
- дополнительные стратегии (`dp`, `price-aware lookahead`, и т.д.)
