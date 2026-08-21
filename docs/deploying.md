# Deploying the backend

One box runs everything server-side. The phone talks to it over HTTPS and
knows nothing about cameras, PostGIS or routing.

    phone --HTTPS--> your box --- FastAPI ---> Supabase (cameras)
                              |            \-> Google (places, ETAs)
                              \- Valhalla (localhost only)

## What runs on it

| | What | Memory |
|---|---|---|
| FastAPI | the four endpoints | ~35 MB |
| Valhalla | routing, in Docker, with the region's tiles | ~600 MB |
| cron | nightly camera ingestion, a couple of minutes | transient |

Measured on the DMV tile set. A 2 GB box works; 4 GB is comfortable and
leaves room for a second region.

Not on the box: Metro, which is a build tool that runs on your laptop and
never in production. Postgres, which Supabase hosts. And the tile *build*,
which needs 1.5 GB and happens on your machine - the server only ever
receives the finished `valhalla_tiles.tar`.

## The one that will catch you: HTTPS is not optional

Android blocks plain HTTP from release builds. Development builds allow it,
which is why `http://192.168.1.190:8000` works today and will stop working
the moment you hand someone a preview APK.

So the backend needs a real certificate, which needs a domain name. Caddy
does both with no configuration to speak of:

    yourdomain.com {
        reverse_proxy localhost:8000
    }

It fetches and renews a Let's Encrypt certificate on its own. Nginx works
too and is more work.

## Valhalla must not be public

Locally it runs on `8003` and that is fine. On a server, bind it to
localhost so only FastAPI can reach it:

    docker run -d --name valhalla-dmv -p 127.0.0.1:8003:8002 ...

An open routing engine is free compute for anyone who finds it, and it
will be found.

Firewall: 80 and 443 open, 22 for you, nothing else. Not 8000, not 8003 -
both sit behind Caddy or behind localhost.

## Keeping FastAPI running

`uvicorn` in a terminal dies when the terminal does. Use systemd:

    [Unit]
    Description=flock-off backend
    After=network.target

    [Service]
    WorkingDirectory=/opt/flock-off/backend
    EnvironmentFile=/opt/flock-off/.env
    ExecStart=/opt/flock-off/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
    Restart=always
    User=flockoff

    [Install]
    WantedBy=multi-user.target

`Restart=always` matters: a crash at 3am should not be an outage until you
notice.

Note `--host 127.0.0.1`, not `0.0.0.0`. Caddy is the only thing that needs
to reach it.

## Secrets

The `.env` stays on the server, readable only by the service user, and is
never committed - the Google key in particular is billable to you and the
database URL is full write access to the camera table.

    DATABASE_URL=postgresql://...      # Supabase session pooler
    VALHALLA_URL=http://localhost:8003
    GOOGLE_API_KEY=...

Restrict the Google key to the server's IP in the Cloud console. A leaked
key that only works from one address is a much smaller problem.

Once the box has a fixed IP, add it plus your home address to Supabase's
network restrictions. Right now the database accepts connections from
anywhere.

## The nightly ingestion

    30 3 * * * cd /opt/flock-off/ingestion && /opt/flock-off/.venv/bin/python -m ingestion.ingest --region dmv --database-url "$DATABASE_URL" >> /var/log/flock-off-ingest.log 2>&1

Roughly two minutes for the DMV against the public Overpass instance,
which is polite at that size. It is idempotent, so a failed run costs
nothing but a retry, and cameras that vanish are marked inactive rather
than deleted.

## Updating the tiles

Rarely - roads change slowly. Build on your laptop, copy the tarball up,
restart the container:

    python infra/valhalla/build_tiles.py --region dmv --work C:/valhalla
    scp C:/valhalla/dmv/custom_files/valhalla_tiles.tar box:/opt/valhalla/
    ssh box docker restart valhalla-dmv

With `force_rebuild=False` and no `tile_urls`, the container memory-maps
the tarball and serves in seconds.

## Pointing the app at it

`EXPO_PUBLIC_API_URL` is frozen into the binary at build time, so it has to
be right before you build anything for anyone else:

    EXPO_PUBLIC_API_URL=https://yourdomain.com npx eas build --profile preview --platform android

Getting this wrong is not an error message. The app silently falls back to
its mock data and looks like it works, showing six fake Fairfax places.

## What to check once it is up

    curl https://yourdomain.com/health
    curl -X POST https://yourdomain.com/plan -H 'content-type: application/json' \
      -d '{"origin":{"lat":38.8462,"lng":-77.3064},"destination":{"lat":38.9531,"lng":-77.4565}}'

A sensible plan has a handful of cameras, an ETA delta of a few minutes,
and waypoints only when something was avoided. Hundreds of cameras or a
twenty minute delta means the region's bounding box is too tight - see
[adding-a-region.md](adding-a-region.md).
