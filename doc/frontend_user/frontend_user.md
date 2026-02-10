# Frontend User Service

## Purpose
Next.js user UI.

## Image
- Built from `frontend-user/Dockerfile`

## Container
- `manifeed_frontend_user`

## Environment
- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)

## Ports
- `3000` inside container
- Host mapping: `USER_PORT` (default `3001`)

## Volumes
- `./frontend-user:/app`
- `user_node_modules:/app/node_modules`

## Dependencies
- `backend`
