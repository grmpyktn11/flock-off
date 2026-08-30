# Deploying the backend

One box runs everything. The phone talks HTTPS to it.

    phone --HTTPS--> your box --- FastAPI ---> Supabase (cameras)
                              |            \-> Google (places, ETAs)
                              \- Valhalla (localhost only)

Sizing: FastAPI ~35 MB, Valhalla ~600 MB for DMV tiles. 2 GB works, 4 GB
is comfortable. Postgres lives on Supabase, not the box. Tiles are built
on your laptop; the server only receives the tarball.

## HTTPS is required

Android release builds block plain HTTP. You need a domain and a cert.
Caddy does both automatically:

    yourdomain.com {
        reverse_proxy localhost:8000
    }

## Keep Valhalla private

Bind it to localhost:

    docker run -d --name valhalla-dmv -p 127.0.0.1:8003:8002 ...

Firewall: 80, 443, and 22 open. Nothing else.

## Run FastAPI under systemd

    [Unit]
    Description=flock-off backend
    After=network.target

    [Service]
    WorkingDirectory=/opt/flock-off/backend
    EnvironmentFile=/opt/flock-off/.env
    ExecStart=/opt/flock-off/.venv/bin/uvicorn app.main:app \
      --host 127.0.0.1 --port 8000 \
      --proxy-headers --forwarded-allow-ips 127.0.0.1
    Restart=always
    User=flockoff

    [Install]
    WantedBy=multi-user.target

- `--host 127.0.0.1`: only Caddy needs to reach it.
- The proxy flags are required. Without them every caller shares one rate
  limit bucket.
- No `--workers`. Rate limit counters are in-process; a second worker
  doubles every limit.

## Secrets

`.env` stays on the server, readable only by the service user:

    DATABASE_URL=postgresql://...      # Supabase session pooler
    VALHALLA_URL=http://localhost:8003
    GOOGLE_API_KEY=...
    APP_KEY=...                        # secrets.token_urlsafe(32)

- `APP_KEY` must match `EXPO_PUBLIC_APP_KEY` in the build profile, or
  every request gets 401. Unset means open (local dev).
- Restrict the Google key to the server's IP in the Cloud console.
- Add the box and your home IP to Supabase network restrictions.

## Protect the billed endpoints

Every request becomes a billed Google call. Three layers:

| Layer | Stops |
|---|---|
| `X-App-Key` | scanners |
| Rate limit per IP | one address hammering you |
| Google daily quota | everything, the hard stop |

Set the Google per-API daily quota in the Cloud console before the domain
is public. A budget alert only emails; a quota refuses the call.

Limits: 30/min on `/search` and `/place`, 10/min shared on `/plan` and
`/replan`, per address. `/health` is never limited.

## Nightly ingestion

    30 3 * * * cd /opt/flock-off/ingestion && /opt/flock-off/.venv/bin/python -m ingestion.ingest --region dmv --database-url "$DATABASE_URL" >> /var/log/flock-off-ingest.log 2>&1

Idempotent. About two minutes for the DMV.

## Updating tiles

Rarely needed. Build locally, ship, restart:

    python infra/valhalla/build_tiles.py --region dmv --work C:/valhalla
    scp C:/valhalla/dmv/custom_files/valhalla_tiles.tar box:/opt/valhalla/
    ssh box docker restart valhalla-dmv

## Point the app at it

`EXPO_PUBLIC_API_URL` is frozen into the binary at build time. Set it in
`mobile/eas.json`, not your shell (EAS builds on its own machines):

    "preview": {
      "env": { "EXPO_PUBLIC_API_URL": "https://yourdomain.com" }
    }

    npx eas build --profile preview --platform android

Getting this wrong is silent: the app falls back to mock data and shows
six fake Fairfax places.

## Verify

    curl https://yourdomain.com/health
    curl -X POST https://yourdomain.com/plan \
      -H 'content-type: application/json' -H "x-app-key: $APP_KEY" \
      -d '{"origin":{"lat":38.8462,"lng":-77.3064},"destination":{"lat":38.9531,"lng":-77.4565}}'

Good: a handful of cameras, a delta of a few minutes. See
[adding-a-region.md](adding-a-region.md).
