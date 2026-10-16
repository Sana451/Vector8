# Vector8 Frontend

The frontend is built with [Vite](https://vitejs.dev/), [React](https://react.dev/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router), [Tailwind CSS](https://tailwindcss.com/), and [shadcn/ui](https://ui.shadcn.com/).

## Requirements

- [Bun](https://bun.sh/)

## Quick Start

From the project root, install the dependencies and start the frontend development server:

```bash
bun install
bun run dev
```

Then open <http://localhost:5173/> in your browser.

Run `uv run bash scripts/prestart.sh` and `uv run fastapi dev` from the `backend` directory, with PostgreSQL running in Docker Compose. See [../development.md](../development.md) for the complete setup.

To serve the frontend with FastAPI, run `bun run build` from the `frontend` directory and open `http://localhost:8000`.

Check `frontend/package.json` to see the other available commands.

## Removing the Frontend

If you are developing an API-only app and want to remove the frontend, you can do it easily:

* Remove the `./frontend` directory.

* In the `backend/app/main.py` file, remove the `app.frontend()` call.

* In the `backend/Dockerfile` file, remove the frontend build stage and the `COPY --from=frontend-build` instruction.

* In the `compose.override.yml` file, remove the `playwright` service.

* In the `.github/workflows/deploy.yml` file, remove the **Set up Bun**, **Install frontend dependencies**, and **Build frontend** steps.

* In the `.fastapicloudignore` file, remove the `!backend/app/frontend/` entry.

Done, you now have an API-only app. 🤓

## Generate Client

### Automatically

* From the project root, run the script:

```bash
bash ./scripts/generate-client.sh
```

* Commit the changes.

### Manually

* Make sure the backend is running.

* Download the OpenAPI JSON file from `http://localhost:8000/api/v1/openapi.json` and copy it to a new file `openapi.json` at the root of the `frontend` directory.

* To generate the frontend client, run:

```bash
bun run generate-client
```

* Commit the changes.

Regenerate the client whenever backend changes affect the OpenAPI schema.

## Using a Remote API

By default, the built frontend uses the same origin as the FastAPI app. If you want to use a remote API while running the Vite development server, you can set the environment variable `VITE_API_URL` to the URL of the remote API. For example, you can set it in the `frontend/.env` file:

```env
VITE_API_URL=https://my-domain.example.com
```

Then, when you run the frontend, it will use that URL as the base URL for the API.

## Code Structure

The frontend code is structured as follows:

* `frontend/src` - The main frontend code.
* `frontend/public` - Static assets.
* `frontend/src/client` - The generated OpenAPI client.
* `frontend/src/components` - The components of the frontend, including the shadcn/ui components in `frontend/src/components/ui`.
* `frontend/src/hooks` - Custom hooks.
* `frontend/src/lib` - Shared frontend utilities.
* `frontend/src/routes` - The frontend routes and pages.

## End-to-End Testing with Playwright

The e2e tests create users and vehicles, so they must not run against your development database. The recommended setup uses a separate `app_e2e` database in the same Postgres container, plus separate ports (backend `8001`, Vite `5174`), so it does not touch `app`/`app_test` and does not conflict with `fastapi dev` (8000) / `bun run dev` (5173) or other projects.

One-time prerequisites:

- `docker compose up -d db mailpit` (same as in `development.md`; Mailpit is used by the password-recovery tests).
- Dependencies installed: `uv sync` in `backend/`, `bun install` in the project root.
- Playwright browsers installed: `bunx playwright install chromium` (from `frontend/`).
- Root `.env` contains `POSTGRES_PASSWORD`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, and `frontend/.env` contains `MAILPIT_HOST=http://localhost:8025`.
- Your usual `fastapi dev` / `bun run dev` may keep running; the e2e stack below uses other ports.

1. Create and migrate the e2e database and the first superuser (from `backend/`, safe to repeat):

```bash
cd backend
set -a; source ../.env; set +a
export E2E_DB=postgresql://postgres:${POSTGRES_PASSWORD}@localhost:5432/app_e2e
TEST_DATABASE_URL=$E2E_DB uv run python scripts/init_test_db.py
DATABASE_URL=$E2E_DB uv run python app/initial_data.py
```

2. Start the backend against `app_e2e` (`FASTAPI_ENV=development` is required: tests create users via the private API; `FRONTEND_HOST` must match the Vite origin for CORS):

```bash
DATABASE_URL=$E2E_DB FASTAPI_ENV=development FRONTEND_HOST=http://localhost:5174 \
  uv run fastapi run --port 8001
```

3. Start the frontend pointing to that backend (from `frontend/`, another terminal):

```bash
VITE_API_URL=http://localhost:8001 bun run dev --port 5174 --strictPort
```

4. Run the tests (third terminal). **You must run them from the `frontend/` directory** (`cd frontend`): the Playwright config lives there, and running `bunx playwright test` from the project root makes every test fail with `Cannot navigate to invalid URL`. `PLAYWRIGHT_BASE_URL` disables Playwright's own web server; `VITE_API_URL` is used by the test helpers; `NO_PROXY` is needed if you have `HTTP_PROXY` set in your shell:

```bash
export NO_PROXY=localhost,127.0.0.1
VITE_API_URL=http://localhost:8001 PLAYWRIGHT_BASE_URL=http://localhost:5174 bunx playwright test
# or with UI
VITE_API_URL=http://localhost:8001 PLAYWRIGHT_BASE_URL=http://localhost:5174 bunx playwright test --ui
```

In UI mode, make sure both projects (`setup` and `chromium`) are selected in the `Projects` filter; otherwise only a part of the tests is shown. If the Playwright panel of the IDE plugin shows "No tests", it does not know the config/env: run `--ui` from a regular terminal in `frontend/` (as above) or set the plugin's working directory to `frontend/` and add the env vars `VITE_API_URL` and `PLAYWRIGHT_BASE_URL`.

If `frontend/test-results` is owned by root (created earlier by the Docker `playwright` service), run `sudo chown -R $USER frontend/test-results` or pass `--output=/tmp/pw-results`.

To reset only the e2e data (never run this against `app`):

```bash
docker compose exec db psql -U postgres -c "DROP DATABASE app_e2e"
```

then repeat step 1.

### Docker variant

`docker compose run --rm backend bash scripts/prestart.sh` followed by `docker compose up -d --wait backend` runs the backend in Docker against the **development** database `app` on port 8000 (it conflicts with a local `fastapi dev`). The `backend` service uses the pre-built `backend:latest` image; if it is stale you will get `Can't locate revision identified by '...'` because the image lacks new migrations. Fix it with `docker compose build backend` (the DB volume is not affected). Use `docker compose down -v` only if you intentionally want to delete all data.

To update the tests, navigate to the tests directory and modify the existing test files or add new ones as needed.

For more information on writing and running Playwright tests, refer to the official [Playwright documentation](https://playwright.dev/docs/intro).
