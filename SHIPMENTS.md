# Shipments

Upload a rate confirmation PDF, review the parsed fields next to the original, then plan a trip from it.

## Flow

1. **Upload** (`/shipments`): `POST /shipments/upload`. The PDF is stored in the database (`bytea`) and parsed by an LLM into broker, rate, weight, equipment and pickup/dropoff stops. Duplicate files (same hash) open the existing shipment.
2. **Review** (`/shipments/{id}`): the original PDF is shown beside an editable form. Low-confidence fields are flagged. Saving marks the shipment as edited; **Re-parse** replaces manual edits.
3. **Plan trip**: choose a vehicle (ranked by distance from its latest position to the first pickup), enter fuel on board, and the system builds a route `current position → pickup → … → last stop` with fuel stops optimised on top. The resulting trip plan has `pickup`/`dropoff` stops (map markers P / U).

## Vehicle position

`vehicle_positions` stores history; the latest row is used. Positions older than 24 h are marked stale. Today positions are entered manually (`POST /vehicles/{id}/position`, or origin coordinates in the plan dialog). Sensor data can later write rows with another `source`; the last shipment's drop-off can serve as a cross-check.

## API

- `GET /shipments/{id}/vehicle-suggestions`
- `POST /shipments/{id}/plan`
- `GET|POST /vehicles/{id}/position`

## Known limitations / TODO

- Parsing runs synchronously in the request; move it to Celery for large files.
- Files live in Postgres; move to S3-compatible storage.
- The parser was verified live on only a subset of the sample documents.
- The map page does not yet offer a shipment selector; plan from the shipment page.
