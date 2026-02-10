# Frontend Admin Service

## Purpose
Next.js admin UI.

## Image
- Built from `frontend-admin/Dockerfile`

## Container
- `manifeed_frontend_admin`

## Environment
- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)

## Ports
- `3000` inside container
- Host mapping: `ADMIN_PORT` (default `3000`)

## Volumes
- `./frontend-admin:/app`
- `admin_node_modules:/app/node_modules`

## Dependencies
- `backend`
