# Frontend Admin Service

## Purpose

`frontend_admin` is the Next.js admin UI for Manifeed operations.

Main areas:
- Health dashboard (`/`)
- RSS catalog management (`/rss`)
- Sources exploration and ingest actions (`/sources`)

## Image and Container

- Image: built from `frontend-admin/Dockerfile`
- Container: `manifeed_frontend_admin`

## Runtime

- Framework: Next.js + React + TypeScript
- Dev command in container: `yarn dev`

## Environment

- `NEXT_PUBLIC_API_URL` (default in compose: `http://localhost:8000`)

## Ports and Volumes

- Internal port: `3000`
- Host mapping: `${ADMIN_PORT:-3000}:3000`
- Volume: `./frontend-admin:/app`

## Backend Dependency

- Depends on `backend` service
- Calls backend HTTP API directly from browser

## API Endpoints Used by UI

Health:
- `GET /health/`

RSS page:
- `GET /rss/`
- `POST /rss/sync`
- `POST /rss/sync?force=true`
- `POST /rss/feeds/check`
- `PATCH /rss/feeds/{feed_id}/enabled`
- `PATCH /rss/companies/{company_id}/enabled`
- `GET /rss/img/{icon_url:path}`

Sources page:
- `GET /sources/`
- `GET /sources/feeds/{feed_id}`
- `GET /sources/companies/{company_id}`
- `GET /sources/{source_id}`
- `POST /sources/ingest`

## Async Job Note

Backend check/ingest endpoints are asynchronous and return `{job_id, status}`.
For full async tracking, UI clients should poll:
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/feeds`

## Useful Commands

- `make up SERVICE=frontend_admin`
- `make logs SERVICE=frontend_admin`
