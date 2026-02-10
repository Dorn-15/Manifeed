# Manifeed
An embedding-based feed engine that clusters articles by meaning instead of keywords.

This project is licensed under the GNU AGPLv3.
Commercial hosting or closed-source usage requires a commercial license.

## What Exists

**Services (Docker Compose)**
- `postgres` (PostgreSQL 15)
- `backend` (FastAPI)
- `frontend_admin` (Next.js Admin)
- `frontend_user` (Next.js User)

**Backend architecture (FastAPI reference layout)**
- `backend/main.py`: FastAPI app + CORS
- `backend/database.py`: SQLAlchemy engine/session
- `backend/alembic`: Alembic migrations
- `backend/app/routers`: thin routers
- `backend/app/services`: orchestration layer
- `backend/app/clients/database`: DB boundaries
- `backend/app/schemas`: API schemas

**Current endpoints**
- `GET /health/` returns `{status, database}`

**Frontend**
- Both frontends are now React + TypeScript (Next.js).
- Minimal pages call `/health` and show API status.

## Run

```bash
make build
make up
```

Default URLs:
- Admin: `http://localhost:3000`
- User: `http://localhost:3001`
- API: `http://localhost:8000/health/`

## Ports Override

```bash
BACKEND_PORT=8001 ADMIN_PORT=3002 USER_PORT=3003 make up
```

## Makefile Commands

Global:
- `make build`
- `make up`
- `make down`
- `make restart`
- `make logs`
- `make clean`
- `make clean-all`
- `make db-migrate`
- `make db-reset`

Per service:
- `make up SERVICE=backend`
- `make logs SERVICE=postgres`

Database:
- `make db-migrate` runs `alembic upgrade head` inside the backend container.
- `make db-reset` downgrades to `base` then upgrades to `head` (drops all tables managed by migrations).

## Environment

Optional variables (Compose):
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `CORS_ORIGINS` (default `*`)
- `NEXT_PUBLIC_API_URL_ADMIN`
- `NEXT_PUBLIC_API_URL_USER`
- `BACKEND_PORT`, `ADMIN_PORT`, `USER_PORT`

## Notes

- DB is not exposed to host by default (no `5432:5432`).
- If you need host access: add `ports: - "5432:5432"` under `postgres`.

## Docs

Per-service notes live in `doc/` (one folder per Docker service).
