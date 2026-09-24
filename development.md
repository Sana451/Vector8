# FastAPI Project - Development

## Local Development

For local development, run PostgreSQL and Mailpit with Docker Compose, and run the FastAPI and Vite development servers locally.

Start the supporting services:

```bash
docker compose up -d db mailpit
```

Then, from the `backend` directory, install the dependencies and prepare the database:

```bash
uv sync
uv run bash scripts/prestart.sh
```

Prepare the isolated pytest database separately:

```bash
cd backend
uv run python scripts/init_test_db.py
```

This keeps `DATABASE_URL` pointed at the development database (`app`) and uses `TEST_DATABASE_URL` for tests (`app_test`).

Start the FastAPI development server:

```bash
uv run fastapi dev
```

In another terminal, from the project root, install the frontend dependencies and start the Vite development server:

```bash
bun install
bun run dev
```

Now you can open these URLs:

Frontend development server: <http://localhost:5173>

Backend API: <http://localhost:8000>

Automatic interactive API documentation with Swagger UI: <http://localhost:8000/docs>

Mailpit: <http://localhost:8025>

The frontend development server uses the backend at `http://localhost:8000`, as configured in `frontend/.env`.

**Note**: In local development mode, Adminer, Traefik, and other services are not running. If you need database administration tools, either:
- Run the full stack with `docker compose watch` instead, which includes Adminer at <http://localhost:8080>
- Or add Adminer to your local services: `docker compose up -d db mailpit adminer`

## PostGIS

This project uses PostGIS for spatial data support. PostGIS is automatically enabled when the database starts.

### Verifying PostGIS Installation

To verify that PostGIS is available in your database, run:

```bash
docker compose exec db psql -U postgres -d app -c "SELECT PostGIS_Version();"
```

Expected output:

```
       postgis_version
─────────────────────────────────
 3.6.0 USE GEOS=3.12.1 CAPI=1.18.0
(1 row)
```

### Testing Spatial Functions

Test creating a point with SRID (WGS84):

```bash
docker compose exec db psql -U postgres -d app -c "
SELECT ST_AsText(
    ST_SetSRID(ST_Point(-97.6386, 39.8379), 4326)
);"
```

Expected output:

```
           st_astext
──────────────────────────────
 POINT(-97.6386 39.8379)
(1 row)
```

Test calculating distance in meters (using geography type):

```bash
docker compose exec db psql -U postgres -d app -c "
SELECT ST_Distance(
    ST_SetSRID(ST_Point(0, 0), 4326)::geography,
    ST_SetSRID(ST_Point(1, 1), 4326)::geography
);"
```

### Using GeoAlchemy2 in Models

Define spatial models with proper SRID and spatial indexing:

```python
from sqlalchemy import Column
from geoalchemy2 import Geometry
from sqlmodel import SQLModel, Field

class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # Point geometry in WGS84 (EPSG:4326) with GIST spatial index
    geom: Geometry = Field(
        sa_column=Column(
            Geometry("POINT", srid=4326, spatial_index=True)
        )
    )
```

For US applications, always use `srid=4326` (WGS84) and enable `spatial_index=True`.

### Frontend Served by FastAPI

Build the frontend from the `frontend` directory:

```bash
bun run build
```

The build is written to `backend/app/frontend` and served by FastAPI at <http://localhost:8000>. Rebuild the frontend after making frontend changes.

## Full Stack with Docker Compose

To run the backend and built frontend in Docker Compose:

```bash
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

Now you can open these URLs:

Application, with the frontend and API served by FastAPI: <http://localhost:8000>

Automatic interactive API documentation with Swagger UI: <http://localhost:8000/docs>

Adminer, database web administration: <http://localhost:8080>

Traefik UI, to see how the routes are being handled by the proxy: <http://localhost:8090>

Mailpit: <http://localhost:8025>

Stop a locally running FastAPI server before starting the Compose backend because both use port `8000`.

**Note**: The first time you start the stack, it might take a minute for all the services to be ready. To monitor it, use `docker compose logs`, or `docker compose logs backend` for the backend service.

## Mailpit

[Mailpit](https://mailpit.axllent.org) captures emails sent during local development instead of delivering them. The local backend connects to it at `localhost:1025`, and the Compose backend connects to the `mailpit` service. Captured emails are available at <http://localhost:8025>.

## Docker Compose Files and Environment Variables

The main `compose.yml` file contains the configuration shared by the whole stack. Docker Compose loads it automatically.

The `compose.override.yml` file adds local development settings, such as mounting the source code as a volume. Docker Compose also loads it automatically and applies it on top of `compose.yml`.

The `compose.deploy.yml` file contains the deployment-specific settings, including HTTPS and automatic certificate handling. It is explicitly combined with `compose.yml` when deploying the application.

The backend reads local settings from the `.env` file. Docker Compose also uses it for variable interpolation and passes the settings each container needs.

After changing variables, make sure you restart the stack:

```bash
docker compose watch
```

## The `.env` File

The tracked `.env` file contains local development defaults, passwords, and other configuration. Its hostnames use `localhost` for processes running on your machine. Docker Compose overrides hostnames such as the database and SMTP server with their Compose service names.

Do not store deployment secrets in `.env`. Configure them as described in the [FastAPI Cloud deployment guide](./deployment.md) or the [Docker Compose deployment guide](./deployment-docker-compose.md).

## Pre-commit Hooks and Code Linting

The project uses [prek](https://prek.j178.dev/), a modern alternative to [pre-commit](https://pre-commit.com/), for code linting and formatting.

You can find a file `.pre-commit-config.yaml` with configurations at the root of the project.

### Install `prek` to Run Automatically

`prek` is already part of the dependencies of the project.

From the project root, install the Git hook so that `prek` runs automatically before each commit:

```bash
uv run prek install -f
```

The `-f` flag forces the installation, in case there was already a `pre-commit` hook previously installed.

Now whenever you try to commit, for example with:

```bash
git commit
```

`prek` will check and format the code you are about to commit. If it modifies any files, add those files to Git again before committing.

### Run `prek` Manually

You can also run `prek` manually on all files from the project root:

```bash
uv run prek run --all-files
```
