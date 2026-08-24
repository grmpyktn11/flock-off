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
    ExecStart=/opt/flock-off/.venv/bin/uvicorn app.main:app \n      --host 127.0.0.1 --port 8000 \n      --proxy-headers --forwarded-allow-ips 127.0.0.1
    Restart=always
    User=flockoff

    [Install]
    WantedBy=multi-user.target

`Restart=always` matters: a crash at 3am should not be an outage until you
notice.

Note `--host 127.0.0.1`, not `0.0.0.0`. Caddy is the only thing that needs
to reach it.

The two proxy flags are not optional either. Without them every request
arrives looking like it came from Caddy on `127.0.0.1`, so all callers
share one rate limit bucket and the first busy minute locks out everyone.
`app/ratelimit.py` reads the address those flags produce.

No `--workers`. The rate limit counters live in the process, so a second
worker would get its own set and silently double every limit. That wants a
shared store before it wants more workers, and one worker is ample here.

## Secrets

The `.env` stays on the server, readable only by the service user, and is
never committed - the Google key in particular is billable to you and the
database URL is full write access to the camera table.

    DATABASE_URL=postgresql://...      # Supabase session pooler
    VALHALLA_URL=http://localhost:8003
    GOOGLE_API_KEY=...
    APP_KEY=...                        # secrets.token_urlsafe(32)

`APP_KEY` has to match `EXPO_PUBLIC_APP_KEY` in the build profile that
produced the APK, or every request comes back 401. Leave it unset and the
service is open, which is the local development case.

Restrict the Google key to the server's IP in the Cloud console. A leaked
key that only works from one address is a much smaller problem.

Once the box has a fixed IP, add it plus your home address to Supabase's
network restrictions. Right now the database accepts connections from
anywhere.

## Protecting the billed endpoints

Every request this service serves becomes at least one billed Google call,
and the app carries no account to bill it to. Three layers, and each
catches what the others miss:

| Layer | Stops | Misses |
|---|---|---|
| `X-App-Key` | scanners that find a URL and go no further | anyone who unzips the APK |
| Rate limit, per IP | one address hammering you | a botnet, or carrier NAT crowds |
| Google daily quota | everything, absolutely | nothing - it is the hard stop |

The first two are in `app/appkey.py` and `app/ratelimit.py`. The third is
not in this repo at all, and it is the one that actually guarantees your
bill: Cloud console, APIs & Services, per-API daily quota limits on Routes
and Places. A budget alert only emails you; a quota refuses the call.

Set that quota before the domain is public. The other two reduce how often
it gets tested.

Limits are 30/minute on `/search` and `/place`, and 10/minute shared
between `/plan` and `/replan`, per address. Deliberately loose: mobile
carriers put many subscribers behind one public address, so a dozen
strangers can share an IP, and a tighter limit would lock them out of each
other's trips. Loose still costs a scraper everything, because what it
wants is thousands a minute. `/health` is never limited so uptime checks
work.

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
be right before you build anything for anyone else. It lives in the build
profile, not in your shell:

    // mobile/eas.json
    "preview": {
      "env": { "EXPO_PUBLIC_API_URL": "https://yourdomain.com" },
      ...
    }

Then:

    npx eas build --profile preview --platform android

Setting it in the shell instead does nothing. EAS runs the build on its own
machines, which never see your terminal, so the variable has to travel in
`eas.json` or in EAS environment variables (`eas env:create`). The URL is
not a secret - it ships inside every APK - so `eas.json` is the simpler
home for it.

Getting this wrong is not an error message. The app silently falls back to
its mock data and looks like it works, showing six fake Fairfax places.

## What to check once it is up

    curl https://yourdomain.com/health
    curl -X POST https://yourdomain.com/plan \
      -H 'content-type: application/json' -H "x-app-key: $APP_KEY" \
      -d '{"origin":{"lat":38.8462,"lng":-77.3064},"destination":{"lat":38.9531,"lng":-77.4565}}'

A sensible plan has a handful of cameras, an ETA delta of a few minutes,
and waypoints only when something was avoided. Hundreds of cameras or a
twenty minute delta means the region's bounding box is too tight - see
[adding-a-region.md](adding-a-region.md).
