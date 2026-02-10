# Backend Service

## Purpose
FastAPI API server and database access layer.

## Image
- Built from `backend/Dockerfile`

## Container
- `manifeed_backend`

## Environment
- `DATABASE_URL` (default `postgresql://manifeed:manifeed@postgres:5432/manifeed`)
- `CORS_ORIGINS` (default `*`)

## Ports
- `8000` inside container
- Host mapping: `BACKEND_PORT` (default `8000`)

## Volumes
- `./backend:/app`

## Dependencies
- `postgres` (waits for healthcheck)

## Endpoints
- `GET /health/`

## Migrations
- `make db-migrate` runs `alembic upgrade head`
- `make db-reset` downgrades to `base` then upgrades to `head`
- Manual: `docker compose exec backend alembic upgrade head`
