#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/lessonlink}"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker

cd "$APP_DIR"
chmod 600 .env.production
sudo docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
sudo docker compose --env-file .env.production -f docker-compose.production.yml ps
