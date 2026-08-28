# flock-off

Driving navigation that plans routes around Flock ALPR and fixed speed
cameras, then hands the route to Google Maps so Google does the
turn-by-turn. While you drive it warns you about the cameras the route
could not avoid.

Currently serving the DMV: Northern Virginia, DC and Maryland, 2,890
cameras. **Adding your own city is one entry in `regions.json` and two
commands** - see [docs/adding-a-region.md](docs/adding-a-region.md).


## How it works

1. You search for a destination. The backend proxies Google Places.
2. `POST /plan` asks Google for the route you would otherwise drive, finds
   which cameras watch it, and asks Valhalla for a route that stays out of
   their dead zones.
3. It converts that detour into Google Maps waypoints, checks Google will
   actually follow them, and returns a deep link.
4. You tap it, Google navigates, and the app watches from the background
   to warn you about any camera it could not route around.

Valhalla exists in this stack for exactly one reason: it is the only
engine that will route around a polygon. Everything the driver sees -
the route, the ETA, the navigation - is Google's, because Google is what
does the driving.

## Layout

| Path | What it is |
|---|---|
| `regions.json` | Every region the project serves. The only file a new city touches. |
| `mobile/` | React Native + Expo app (SDK 54). |
| `web/` | The showcase site: camera map and precomputed route demos, deployed to GitHub Pages. Data is exported once by `web/scripts/` and committed, so the site costs nothing to serve. |
| `backend/` | FastAPI: `/search`, `/place`, `/plan`, `/replan`, `/health`. |
| `ingestion/` | Overpass camera ingestion, dead zone geometry, `schema.sql`. |
| `infra/valhalla/` | Routing tile build and its smoke test. |
| `docs/` | The spec, findings worth keeping, and the deferred list. |

## Running it

Each source is real when its credential is set and mocked otherwise, so a
fresh checkout runs with no infrastructure at all and you can switch on
one piece at a time. Put credentials in `.env` at the repo root:

```
DATABASE_URL=postgresql://...     # Postgres + PostGIS. Session pooler on Supabase.
VALHALLA_URL=http://localhost:8003
GOOGLE_API_KEY=...                # Places API (New) and Routes API only.
```

```
cd backend    && pip install -r requirements.txt && uvicorn app.main:app --reload
cd ingestion  && pip install -r requirements.txt && python -m pytest tests -q
cd mobile     && npm install && npm start
```

The app talks to the backend when `EXPO_PUBLIC_API_URL` is set and uses
its own mock otherwise.

## What works, and what has not been driven

`/plan` runs end to end on live services and the numbers are honest: a
Fairfax trip avoids 0-1 cameras at a cost of 0-2.5 minutes, and a trip
whose cameras cannot be dodged says so rather than claiming otherwise.

The drive-time half - foreground service, background GPS, spoken warnings,
the off-route prompt - is written and its logic is tested, but **it has
never run on a phone**. None of it works in Expo Go; it needs an EAS
development build. Treat it as unverified until someone drives it.

Two things worth reading before changing anything:

- [docs/eta-delta.md](docs/eta-delta.md) - why both ETAs come from Google,
  and why comparing engines quietly reported avoiding two cameras as a
  three-minute *saving*.


## Contributing a region

Camera coverage in OpenStreetMap is contributed by people, so a thin count
means thin mapping rather than an absence of cameras. If your area is
sparse, the most useful contribution is not code: it is mapping the
cameras into OSM, where this project and everyone else's picks them up.
