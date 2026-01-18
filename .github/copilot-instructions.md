# Copilot / Agent Quick Guide for NPO API ✅

## Brief summary
- **What:** FastAPI backend that ingests and organizes high-resolution images (RAW/JPEG/etc.), computes hashes, stores tiled image pyramids (DZI), and exposes retrieval endpoints.
- **Why:** Provide a resilient image store with duplicate detection (perceptual/pixel hashes), metadata extraction and tile-serving for high-resolution zooming.

## Key components & where to look 🔎
- App entry: [`src/npo/main.py`](../src/npo/main.py) – sets up FastAPI, middleware, lifespan that runs migrations via `init_db()`.
- Configuration: [`src/npo/core/config.py`](../src/npo/core/config.py) – settings via `.env` (`npo_` prefix); split into backend/frontend settings.
- Image logic: [`src/npo/images/services.py`](../src/npo/modules/images/services.py) – hashing, EXIF extraction, DZI creation, file movement.
- API routes: `src/npo/images/routes.py` – upload, full image, metadata, tile endpoints; other routers: `src/npo/settings/routes.py`, `src/npo/health/routes.py`.
- DB layer: [`src/npo/core/database.py`](../src/npo/core/database.py) – async SQLAlchemy setup; `init_db()` runs Alembic migrations. File models: [`src/npo/images/models.py`](../src/npo/modules/images/models.py).
- Tests & fixtures: [`tests/conftest.py`](../tests/conftest.py) – client fixtures, `TEST_DATABASE_URL`, `USE_ALEMBIC_MIGRATIONS`, `seed_data`, temp dirs.

## Important conventions & patterns ⚙️
- Hash-based storage: Pixel hash is broken into directory chunks using `NPO_HASH_DIR_STEP` and `NPO_HASH_DIR_PARTS_COUNT` from `config.settings`. See `compute_hash_pathes()` in `services.py` for exact behavior.
- Two hash kinds for dedup: **perceptual_hash** (dHash via pyvips, 16 hex chars) and **pixel_hash** (BLAKE2b over pixel bytes, 32 hex). See `compute_perceptual_hash()` and `compute_pixel_hash()`.
- File model: `src/npo/modules/images/models.py` — fields include `file_hash` (md5), `perceptual_hash`, `pixel_hash`, `meta_data` (JSON), location fields (`path_hash_dir`, `path_hash_file`). DB table names are `classname.lower() + 's'` (see `Base.__tablename__`).
- DZI tiles: generated with pyvips and saved as `.szi` (ZIP container). Tiles read from ZIP (`get_tile_from_dzi`).
- Error handling: use `APIException` with `ErrorCode` constants (`npo/constants.py`) to ensure consistent `code` and `message` structure in responses. Prefer `ErrorCode.X.formatMsg(...)` to populate messages and validate required fields.
- Routes: prefer the `NpoApiRoute()` helper (in `src/npo/common/decorators.py`) to get standard `responses` and override examples.
- i18n: messages use `fastapi_babel`/`BabelMiddleware`; localized strings use `_()`.

## Developer workflows & commands 🧰
- Requirements: Python >= 3.13 (see `pyproject.toml`) and system `exiftool` (README indicates `exiftool --version`). Image processing uses `pyvips` (binary wheel used), and `python-magic`.
- Install & dev: uses `uv` (Astral) package manager. From project root:
  - `uv sync --locked --all-extras --dev`
  - `cp .env.sample .env` and edit as needed
  - `uv run fastapi dev src/npo/main.py` (runs app and triggers `init_db()` → Alembic migrations)
- Migrations: Alembic config is in `pyproject.toml` (`[tool.alembic]`). App startup runs `alembic upgrade head` via `init_db()`; tests can set `USE_ALEMBIC_MIGRATIONS=True` to use migrations in fixtures.
- Tests: run `uv run pytest` (or `uv run pytest --cov --cov-report=html`).
  - Default tests use an in-memory SQLite DB. To run against Postgres for tests, set `TEST_DATABASE_URL` in `.env.test` and `USE_ALEMBIC_MIGRATIONS=True`.
  - Tests use HTTPX `AsyncClient` with `ASGITransport` and override `get_session` dependency in `conftest.py`.
  - Large test assets are cached in `tests/.cache` and seeded via `seed_data` fixture; a `skip_seed` marker is supported.

## Quick examples to reference (copy/paste) ✂️
- Upload endpoint (single or multipart): POST `/images/upload` ➜ handled in `src/npo/modules/images/routes.py` (look for `files_route` and `NpoApiRoute`).
- Tile retrieval: GET `/{pixel_hash}/{zoom}/{x}/{y}.jpg` ➜ handled in `src/npo/modules/images/routes.py` and served from `.szi` (ZIP DZI) via `get_tile_from_dzi` in `src/npo/modules/images/services.py`.
- Hash lookups: CRUD helpers use `ilike(f"{hash}%")` prefix matching — see `get_file_by_pixel_hash` and `get_file_by_perceptual_hash` in `src/npo/modules/images/crud.py`.
- Raise a consistent API error (use `ErrorCode` enum and `APIException`):
```python
from npo.common.decorators import APIException
from npo.core.constants import ErrorCode
raise APIException(status_code=404, code=ErrorCode.FILE_NOT_FOUND, message=ErrorCode.FILE_NOT_FOUND.formatMsg(pixel_hash=hash))
```

## Architecture & runtime patterns 🔭
- App: `src/npo/main.py` boots FastAPI and calls `init_db()` which runs Alembic migrations on startup (`src/npo/core/database.py`).
- Async-first: codebase uses `AsyncSession`, `async def` endpoints, and dependency `get_session`. Long-running sync operations (pyvips, hashing) are executed with `loop.run_in_executor`.
- Image flow: upload → compute perceptual & pixel hashes (`src/npo/modules/images/services.py`) → compute directory path chunks (`compute_hash_pathes`) → store file + `.szi` DZI tiles and metadata.

## Storage, hashing & DZI details 🗂️
- Two hashes: `perceptual_hash` (dHash, 16 hex) and `pixel_hash` (BLAKE2b, 32 hex). See `compute_perceptual_hash` / `compute_pixel_hash` in `src/npo/modules/images/services.py`.
- Directory layout: governed by `NPO_HASH_DIR_STEP` and `NPO_HASH_DIR_PARTS_COUNT` in settings; splitting pixel hash into chunks for nested directories (`compute_hash_pathes`).
- DZI tiles are stored in `.szi` ZIP container; reading tiles is implemented in `get_tile_from_dzi` (returns preview for missing tiles).
- RAW support: `extract_jpeg_preview` tries to extract a JPEG preview (requires `exiftool` and pyvips); check `python-magic` usage for mime detection.

## Tests, local dev & CI 🧪
- Dev tooling: uses `uv` (Astral). Common commands:
  - `uv sync --locked --all-extras --dev`
  - `cp .env.sample .env` (edit) and `uv run fastapi dev src/npo/main.py`
  - `uv run pytest` or `uv run pytest --cov --cov-report=html`
- Tests default to in-memory SQLite; to run against Postgres set `TEST_DATABASE_URL` and `USE_ALEMBIC_MIGRATIONS=True` (see `tests/conftest.py`).
- Testing utilities: HTTPX `AsyncClient` with `ASGITransport` and dependency overrides for `get_session`; large test assets live in `tests/.cache` and are seeded by the `seed_data` fixture.

## PR checklist & quick rules ✅
- Use `NpoApiRoute()` for new routers to keep consistent OpenAPI `responses` and examples.
- Use `ErrorCode` enums and `APIException` for API errors (ensure `formatMsg` variables are provided).
- When adding image processing or new binaries (e.g., exiftool-like tools) document install steps and add CI changes — these are non-trivial for reproducible pipeline builds.
- Add tests for: hash computation, duplicate detection (`check_duplicates_by_perceptual_hash`), tile serving (`get_tile_from_dzi`), and route behaviors.

## Common pitfalls & gotchas ⚠️
- Changing the hashing scheme or directory layout requires migration and careful handling of existing `.szi` assets — involve maintainers early.
- `pixel_hash` and `perceptual_hash` comparisons use prefix `ilike` queries (not full equality); be aware of partial-match behavior in endpoints and tests.
- CPU-bound work (pyvips, hashing) runs in executors — be careful when writing sync helpers not to block the event loop.

---
If anything here is unclear or you want the PR checklist expanded into a template (CI steps, steps to add a migration, test templates), tell me which sections to expand and I'll update this file. ✅
