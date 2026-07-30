# BC Workspace — Production Foundation

This deployment contains four services:

- PostgreSQL 16 with pgvector
- FastAPI backend
- Next.js frontend
- Caddy reverse proxy with HTTPS

Public routing:

    https://APP_DOMAIN/       -> Next.js
    https://APP_DOMAIN/api/*  -> FastAPI

PostgreSQL is available only on the private Docker network.

## Prepare the production environment

    cp .env.production.example .env.production
    chmod 600 .env.production

Replace every CHANGE_ME value.

Never commit .env.production.

## Validate

    docker compose \
      --env-file .env.production \
      -f docker-compose.production.yml \
      config

## Build

    docker compose \
      --env-file .env.production \
      -f docker-compose.production.yml \
      build

## Start

    docker compose \
      --env-file .env.production \
      -f docker-compose.production.yml \
      up -d

## Status

    docker compose \
      --env-file .env.production \
      -f docker-compose.production.yml \
      ps

## Logs

    docker compose \
      --env-file .env.production \
      -f docker-compose.production.yml \
      logs --tail=200

## Smoke test

    APP_URL=https://copilot.bitcoinchange.co.il \
      ./scripts/smoke-test-production.sh

## Backup

    ./scripts/backup-production-postgres.sh

Authentication, authorization, scheduled Wiki synchronization,
monitoring, scheduled backups and restore automation are not yet
included. They are required before an organization-wide rollout.
