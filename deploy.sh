#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  cp .env.deploy.example .env
fi

docker compose --env-file .env -f compose.deploy.yml up -d --build
docker compose --env-file .env -f compose.deploy.yml ps
