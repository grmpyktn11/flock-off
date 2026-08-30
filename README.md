# flock-off

Navigation that routes around Flock ALPR and speed cameras, then hands
the route to Google Maps for turn-by-turn. While you drive it warns you
about cameras the route could not avoid.

Currently serving the DMV: Northern Virginia, DC and Maryland, 2,890
cameras. Adding your own city is one entry in `regions.json` and two
commands. See [docs/adding-a-region.md](docs/adding-a-region.md).

A hosted version is coming soon. Until then, run it locally (below).

## How it works

1. You search for a destination. The backend proxies Google Places.
2. `POST /plan` gets Google's normal route, finds which cameras watch it,
   and asks Valhalla for a route that stays out of their dead zones.
3. The detour becomes Google Maps waypoints, validated so Google actually
   follows them, and comes back as a deep link.
4. You tap it. Google navigates. The app watches from the background and
   warns about any camera it could not route around.

Valhalla is here because it is the only engine that routes around a
polygon. Everything the driver sees is Google's.

## Layout

| Path | What it is |
|---|---|
| `regions.json` | Every region served. The only file a new city touches. |
| `mobile/` | React Native + Expo app (SDK 54). |
| `web/` | Showcase site, GitHub Pages. Data is precomputed and committed. |
| `backend/` | FastAPI: `/search`, `/place`, `/plan`, `/replan`, `/explanations`, `/health`. |
| `ingestion/` | Camera ingestion, dead zone geometry, `schema.sql`. |
| `infra/valhalla/` | Routing tile build and smoke test. |
| `docs/` | Guides and findings. |

## Run it locally

Everything mocks itself when its credential is unset, so a fresh checkout
runs with zero infrastructure.

Backend:

```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

App:

```
cd mobile
npm install
npm start
```

Open the `exp://` URL in Expo Go. With no config the app uses mock data
and needs nothing else running. To point it at your backend:

```
EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000 npm start
```

To use real services, put credentials in `.env` at the repo root. Each
one switches on independently:

```
DATABASE_URL=postgresql://...     # Postgres + PostGIS cameras table
VALHALLA_URL=http://localhost:8003
GOOGLE_API_KEY=...                # Places API (New) and Routes API
ANTHROPIC_API_KEY=...             # camera explanations
CENSUS_API_KEY=...                # income data for explanations
```

To load real cameras and build routing tiles, see
[docs/adding-a-region.md](docs/adding-a-region.md). To put it on a
server, see [docs/deploying.md](docs/deploying.md).

## Status

`/plan` runs end to end on live services. Numbers are honest: a Fairfax
trip avoids 0-1 cameras for 0-2.5 minutes, and a trip that cannot dodge
its cameras says so.

The drive-time half (background GPS, spoken warnings, off-route replan)
is written and unit tested but has not been driven in a car. It needs an
EAS development build; none of it runs in Expo Go.

## Contributing a region

Camera data comes from OpenStreetMap. A thin count means thin mapping,
not no cameras. The most useful contribution is mapping cameras into OSM.
