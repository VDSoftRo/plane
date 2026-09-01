#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Plane (Francu Digital) — host-side deploy script.
#
# Builds and (re)starts the full Plane stack on the Ubuntu host. Run manually
# after pushing code:  ./deploy/deploy.sh
#
# Unlike the pontario-backoffice deploy, Plane has a DB: this script blocks on
# the one-shot `migrator` service and fails the deploy if migrations fail,
# rather than letting a broken schema surface later as a half-working app.
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

COMPOSE_FILE="docker-compose.prod.yml"
BRANCH="${DEPLOY_BRANCH:-production-francu}"
# Set SKIP_GIT=1 to build the working tree as-is (no fetch/reset). Useful when
# testing a change on the host before pushing it.
SKIP_GIT="${SKIP_GIT:-0}"

compose() { docker compose -f "${COMPOSE_FILE}" "$@"; }

log() { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[deploy:error]\033[0m %s\n' "$*" >&2; }

# --- Preconditions -----------------------------------------------------------
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  err "docker / docker compose plugin not available. Install Docker first."
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  err ".env not found at ${REPO_ROOT}/.env — copy .env.example to .env and fill it in."
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/apps/api/.env" ]]; then
  err "apps/api/.env not found — copy apps/api/.env.prod.example to apps/api/.env and fill it in."
  err "It carries WEB_URL / *_BASE_URL / CORS_ALLOWED_ORIGINS, which MUST match the"
  err "public hostname or login and file uploads break. See deploy/README.md."
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/apps/live/.env" ]]; then
  err "apps/live/.env not found — copy apps/live/.env.prod.example to apps/live/.env."
  err "The live server validates its env at startup and exits if API_BASE_URL or"
  err "LIVE_SERVER_SECRET_KEY are missing, so it would just crash-loop."
  exit 1
fi

# LIVE_SERVER_SECRET_KEY is a shared secret between the API and the live server.
# If the two files disagree, both containers start fine and collaborative
# editing silently fails auth on every connection — worth catching up front.
# Reads a KEY=value from an env file, stripping surrounding single/double
# quotes. Returns empty if the key is absent.
read_env_value() {
  sed -n "s/^$2=//p" "$1" | head -1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

api_live_key="$(read_env_value "${REPO_ROOT}/apps/api/.env" LIVE_SERVER_SECRET_KEY)"
live_live_key="$(read_env_value "${REPO_ROOT}/apps/live/.env" LIVE_SERVER_SECRET_KEY)"
if [[ -z "${api_live_key}" || "${api_live_key}" != "${live_live_key}" ]]; then
  err "LIVE_SERVER_SECRET_KEY does not match between apps/api/.env and apps/live/.env."
  err "Collaborative editing would fail auth on every connection. Make them identical."
  exit 1
fi

# The `edge` network is external: compose will not create it, and the error it
# gives ("network edge declared as external, but could not be found") is easy to
# misread. Check up front with an actionable message.
if ! docker network inspect edge >/dev/null 2>&1; then
  err "The shared 'edge' docker network does not exist."
  err "Create it with:  docker network create edge"
  err "Or install the boot units:  sudo /data/devops-francu/systemd/install.sh"
  exit 1
fi

# --- Pull latest code --------------------------------------------------------
if [[ "${SKIP_GIT}" == "1" ]]; then
  log "SKIP_GIT=1 — building the working tree as-is, no fetch/reset."
else
  log "Fetching latest code on '${BRANCH}'..."
  git fetch --prune origin
  git checkout "${BRANCH}"
  git reset --hard "origin/${BRANCH}"
fi
log "Now at commit: $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)"

# --- Build -------------------------------------------------------------------
log "Building images (this takes a while on first run)..."
compose build

# --- Migrate -----------------------------------------------------------------
# Bring up only what migrations need, then run the migrator to completion.
# `run --rm` (rather than `up`) gives us the exit code directly.
log "Starting database and cache..."
compose up -d plane-db plane-redis

log "Running database migrations..."
if ! compose run --rm migrator; then
  err "Migrations FAILED — not starting the rest of the stack."
  err "Inspect with: docker compose -f ${COMPOSE_FILE} run --rm migrator"
  exit 1
fi
log "Migrations applied."

# --- Deploy ------------------------------------------------------------------
log "Starting / updating the full stack..."
# --remove-orphans clears containers left behind by the upstream
# docker-compose.yml (which uses different service names, e.g. `proxy`).
compose up -d --remove-orphans

log "Pruning dangling images..."
docker image prune -f >/dev/null

log "Current status:"
compose ps

cat <<'EOF'

[deploy] Done. Plane should be reachable at http://plane.francugroup.ro

Post-deploy checks:
  docker compose -f docker-compose.prod.yml logs -f api
  curl -sS -o /dev/null -w '%{http_code}\n' -H 'Host: plane.francugroup.ro' http://127.0.0.1/

First deploy only — configure the instance admin, then SMTP:
  http://plane.francugroup.ro/god-mode/email
EOF
