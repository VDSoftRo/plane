# Deploying Plane (Francu Digital)

Plane runs on the Francu/Pontario Ubuntu host, behind the shared Caddy edge
proxy from [`devops-francu`](../../devops-francu), at:

```
http://plane.francugroup.ro
```

## Topology

```
browser (on VPN)
   │
   └── http://plane.francugroup.ro
          │
          ▼
       edge Caddy :80              [devops-francu]
          │  (edge network, dynamic-DNS upstream)
          ▼
       plane-proxy:80              [this repo, apps/proxy]
          ├── /api/*      -> api:8000
          ├── /auth/*     -> api:8000
          ├── /static/*   -> api:8000
          ├── /god-mode/* -> admin:3000
          ├── /spaces/*   -> space:3000
          ├── /live/*     -> live:3000
          ├── /uploads/*  -> plane-minio:9000
          └── /*          -> web:3000
```

Two proxies, on purpose: the edge Caddy routes **by hostname** across all stacks
on the host; Plane's own Caddy routes **by path** within Plane. The edge proxy
has exactly one Plane upstream (`plane-proxy`), so Plane's internal routing is
untouched and future upstream releases don't conflict with it.

Everything except `plane-proxy` sits on the stack-private `plane-net`. Only
`plane-proxy` joins `edge`.

## First-time host setup

```bash
# 1. The shared edge network must exist first (see devops-francu README).
sudo /data/devops-francu/systemd/install.sh     # or: docker network create edge

# 2. Clone
sudo git clone -b production-francu <repo-url> /data/plane
cd /data/plane

# 3. Both env files — BOTH are required.
cp .env.prod.example .env
cp apps/api/.env.prod.example apps/api/.env
$EDITOR .env apps/api/.env      # fill in every CHANGE-ME

# 4. Deploy
./deploy/deploy.sh
```

Generate the two secrets with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
```

### Values that must match across the two files

`.env` feeds the postgres/rabbitmq/minio **containers**; `apps/api/.env` tells
the **application** how to reach them. They are not merged — set both:

| Value                        | `.env` | `apps/api/.env` |
| ---------------------------- | ------ | --------------- |
| Postgres user/password/db    | ✅     | ✅              |
| RabbitMQ user/password/vhost | ✅     | ✅              |
| MinIO access key / secret    | ✅     | ✅              |
| Bucket name                  | ✅     | ✅              |

## CRITICAL: env correlations for the domain

Same class of trap as `BACKOFFICE_ORIGIN` in the devops-francu README. Serving
Plane on a hostname instead of `localhost` changes the browser `Origin`, and
three settings in `apps/api/.env` must agree with it:

```
CORS_ALLOWED_ORIGINS="http://plane.francugroup.ro"
WEB_URL="http://plane.francugroup.ro"
APP_BASE_URL / ADMIN_BASE_URL / SPACE_BASE_URL / LIVE_BASE_URL   (same origin)
```

No trailing slashes — the CORS check is an exact string match.

Failure modes if you get these wrong, none of which look like a proxy problem:

| Wrong value            | Symptom                                                                                                                                                              |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CORS_ALLOWED_ORIGINS` | Login fails; every XHR blocked by CORS in the console                                                                                                                |
| `WEB_URL`              | All avatars/attachments are broken links to `localhost/uploads/...`, because with `USE_MINIO=1` this becomes `AWS_S3_CUSTOM_DOMAIN` (`plane/settings/common.py:314`) |
| `WEB_URL`              | Invite and magic-link emails point at a URL nobody can open                                                                                                          |
| `*_BASE_URL`           | `/god-mode`, `/spaces`, `/live` redirect to `localhost:300x`                                                                                                         |

Env changes need a **recreate**, not a restart:

```bash
docker compose -f docker-compose.prod.yml up -d api worker beat-worker
docker compose -f docker-compose.prod.yml exec api printenv WEB_URL
```

## Routine deploys

```bash
cd /data/plane
./deploy/deploy.sh
```

The script fetches `production-francu`, hard-resets to it, builds, runs
migrations **and fails the deploy if they fail**, then brings the stack up.

Overrides:

```bash
DEPLOY_BRANCH=some-branch ./deploy/deploy.sh   # deploy a different branch
SKIP_GIT=1 ./deploy/deploy.sh                  # build the working tree as-is
```

## Boot persistence

Registered as a `compose-stack@plane` systemd instance in devops-francu, so it
comes up on boot with `--force-recreate` (needed because `edge` gets a new
network ID on every reboot and pinned containers otherwise fail to reattach —
see the devops-francu README).

```bash
systemctl status compose-stack@plane
journalctl -u compose-stack@plane
sudo systemctl start compose-stack@plane   # runs compose up -d for this stack
```

## First boot: instance setup

1. Create the instance admin at `http://plane.francugroup.ro/god-mode`
2. Configure SMTP at `http://plane.francugroup.ro/god-mode/email`, then use
   **Send test email** to verify before inviting anyone.

SMTP is **not** read from env at runtime: `SKIP_ENV_VAR` defaults to `1`, so the
API reads email settings from the `instance_configurations` DB table
(`plane/license/utils/instance_value.py:19`). Env vars only _seed_ that table on
first boot via `manage.py configure_instance`, which uses `get_or_create` — once
the rows exist, env changes are ignored. Use the admin panel.

The SMTP password is stored encrypted with `SECRET_KEY`, so rotating that key
means re-entering it.

## Operations

```bash
cd /data/plane
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f plane-proxy

# Is Plane answering behind the edge proxy?
curl -sS -o /dev/null -w '%{http_code}\n' -H 'Host: plane.francugroup.ro' http://127.0.0.1/

# Django shell
docker compose -f docker-compose.prod.yml exec api python manage.py shell
```

### Backups

The data lives in named volumes (`plane_pgdata`, `plane_uploads`,
`plane_rabbitmq_data`, `plane_redisdata`). Database dump:

```bash
docker compose -f docker-compose.prod.yml exec plane-db \
  pg_dump -U plane plane | gzip > plane-$(date +%F).sql.gz
```

## Troubleshooting

**`network edge declared as external, but could not be found`** — the shared
network is missing. `docker network create edge`, or
`sudo systemctl start docker-edge-network.service`.

**502 from the edge proxy after a redeploy** — the edge Caddyfile uses a
`dynamic a` upstream that re-resolves every 10s, so this should self-heal.
If it persists, check `plane-proxy` is actually attached to `edge`:

```bash
docker network inspect edge --format '{{range .Containers}}{{.Name}} {{end}}'
```

**Migrations fail** — the deploy stops before starting the app. Re-run alone:

```bash
docker compose -f docker-compose.prod.yml run --rm migrator
```

**Port 80 already in use** — the edge Caddy owns `:80` on this host. This stack
must publish nothing; check you're using `docker-compose.prod.yml` and not the
upstream `docker-compose.yml` (which publishes `LISTEN_HTTP_PORT`).

## Why a separate compose file

`docker-compose.prod.yml` sits alongside the upstream `docker-compose.yml`
rather than replacing it, so the `production-francu` branch can merge upstream
`makeplane/plane` releases without conflicting on compose. It differs by:

- no `container_name:` (upstream hardcodes host-global names like `api`, `web`,
  `proxy`, which collide with other stacks on this host)
- `proxy` renamed `plane-proxy` (it's the name the edge Caddy resolves on the
  shared network — `proxy` is too generic to be safe there)
- no published ports; `plane-proxy` listens on `:80` and joins `edge`
- everything else on a private `plane-net`
- healthchecks on `plane-db` and `plane-proxy`
