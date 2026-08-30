"""Public-records enrichment: what is actually happening around each camera.

Fills four columns on the cameras table from free government APIs, so an
explanation can say whether a placement matches the local crime picture
instead of guessing:

- crime_count / crime_desc: reported incidents near the camera.
  * DC: point-radius count against MPD's Crime Incidents layers
    (maps2.dcgis.dc.gov), last 12 months within 800 m. The gold standard.
  * Fairfax County: FCPD's on-demand weekly crime CSV, counted by ZIP -
    the county publishes block-level addresses, not coordinates, so ZIP
    is the honest resolution. crime_desc records which of these was used.
- tract_income / county_income: ACS 5-year median household income for
  the camera's census tract and its county. Needs CENSUS_API_KEY in the
  repo root .env (free, instant: api.census.gov/data/key_signup.html);
  skipped when unset, same rule as every other credential here.

Run:
    python -m ingestion.enrich --database-url postgresql://...
    python -m ingestion.enrich --database-url ... --limit 50

Rows it updates get explanation/explained_at cleared, because a cached
explanation written without these facts is stale the moment they exist.
"""

import argparse
import csv
import io
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HEADERS = {"User-Agent": "flock-off/0.1 (camera-avoiding navigation)"}

# The repo root .env, same file config.py and the backend read.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

RADIUS_M = 800

# MPD publishes one layer per year; the current and previous year together
# cover any trailing 12 months.
DC_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/MPD/MapServer/{layer}/query"
DC_LAYERS = {2025: 7, 2026: 41}
DC_BBOX = (38.79, -77.12, 39.00, -76.90)  # south, west, north, east

FAIRFAX_CSV_URL = "https://www.fairfaxcounty.gov/apps/pfsu/api/file/crimereportsfromsp"

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
ACS_URL = "https://api.census.gov/data/2023/acs/acs5"
MEDIAN_INCOME = "B19013_001E"

# Politeness pause between per-camera API calls. These are public services
# and a regional run is a few hundred cameras, not a scrape.
PAUSE_S = 0.2

# Cameras cluster - several readers at one intersection, a ring around one
# parking lot - and neighbors share the same neighborhood facts. Points
# are snapped to this grid (3 decimals is about 110 m) and each cell asks
# the geocoder and the crime API once; income is one call per census
# tract. Cuts a regional run's API calls by roughly two thirds.
GRID_DECIMALS = 3


def _cell(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, GRID_DECIMALS), round(lng, GRID_DECIMALS))


def load_env() -> None:
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def dc_incident_count(lat: float, lng: float, radius_m: float = RADIUS_M) -> int:
    """Reported MPD incidents within radius_m of the point, last 12 months."""
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    total = 0
    for layer in DC_LAYERS.values():
        response = requests.get(
            DC_URL.format(layer=layer),
            params={
                "geometry": f"{lng},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "distance": radius_m,
                "units": "esriSRUnit_Meter",
                "where": f"REPORT_DAT >= DATE '{since}'",
                "returnCountOnly": "true",
                "f": "json",
            },
            headers=HEADERS,
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        if "count" not in body:
            raise RuntimeError(f"DC layer {layer}: {body}")
        total += body["count"]
    return total


def in_dc(lat: float, lng: float) -> bool:
    south, west, north, east = DC_BBOX
    return south <= lat <= north and west <= lng <= east


def fairfax_weekly_by_zip() -> tuple[dict[str, int], str]:
    """FCPD's latest weekly file as {zip: incident count}, plus the week."""
    response = requests.get(FAIRFAX_CSV_URL, headers=HEADERS, timeout=120)
    response.raise_for_status()
    counts: dict[str, int] = {}
    dates: list[str] = []
    # No header row: n, offense code, offense, date, time, address, city,
    # state, zip.
    for row in csv.reader(io.StringIO(response.text)):
        if len(row) < 9:
            continue
        zip_code = row[8].strip()
        if zip_code:
            counts[zip_code] = counts.get(zip_code, 0) + 1
        if row[3].strip():
            dates.append(row[3].strip())
    week = f"{min(dates)} to {max(dates)}" if dates else "latest week"
    return counts, week


def census_geographies(lat: float, lng: float) -> dict:
    """Tract FIPS, county FIPS/name, and ZCTA for a point. Free, keyless."""
    response = requests.get(
        GEOCODER_URL,
        params={
            "x": lng,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "layers": "all",
            "format": "json",
        },
        headers=HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    geographies = response.json()["result"]["geographies"]

    out: dict = {}
    for name, entries in geographies.items():
        if not entries:
            continue
        entry = entries[0]
        if name == "Census Tracts":
            out["state"] = entry["STATE"]
            out["county"] = entry["COUNTY"]
            out["tract"] = entry["TRACT"]
        elif name == "Counties":
            out["county_name"] = entry.get("NAME")
        elif "ZIP" in name.upper():
            out["zip"] = entry.get("GEOID") or entry.get("ZCTA5")
    return out


def acs_median_income(
    state: str, county: str, tract: str | None, api_key: str
) -> int | None:
    """Median household income for a tract, or the county when tract is None.

    ACS uses large negative sentinels (-666666666) for suppressed values;
    those come back as None here rather than as an absurd number.
    """
    if tract:
        geo = {"for": f"tract:{tract}", "in": f"state:{state} county:{county}"}
    else:
        geo = {"for": f"county:{county}", "in": f"state:{state}"}
    response = requests.get(
        ACS_URL,
        params={"get": MEDIAN_INCOME, **geo, "key": api_key},
        headers=HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    rows = response.json()
    try:
        value = int(rows[1][0])
    except (IndexError, TypeError, ValueError):
        return None
    return value if value > 0 else None


SELECT_SQL = """
    SELECT id, ST_Y(geom), ST_X(geom), operator
    FROM cameras
    WHERE active AND enriched_at IS NULL
    ORDER BY id
"""

UPDATE_SQL = """
    UPDATE cameras
    SET crime_count = %s, crime_desc = %s,
        tract_income = %s, county_income = %s,
        enriched_at = now(),
        explanation = NULL, explained_at = NULL
    WHERE id = %s
"""


def enrich(database_url: str, census_key: str, limit: int | None = None) -> int:
    import psycopg

    fairfax_zip_counts: dict[str, int] | None = None
    fairfax_week = ""
    geo_cache: dict[tuple[float, float], dict] = {}
    dc_count_cache: dict[tuple[float, float], int] = {}
    tract_income_cache: dict[tuple[str, str, str], int | None] = {}
    county_income_cache: dict[tuple[str, str], int | None] = {}

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SQL)
            rows = cur.fetchall()

    updated = 0
    for camera_id, lat, lng, operator in rows:
        if limit is not None and updated >= limit:
            break

        crime_count: int | None = None
        crime_desc: str | None = None
        tract_income: int | None = None
        county_income: int | None = None

        # The geocoder is only worth a call when something downstream can
        # use the answer: the ACS lookups (key set), Fairfax ZIP matching,
        # or confirming a DC-bbox camera is really in the District - the
        # bbox clips Bethesda and Silver Spring, and counting MPD
        # incidents around a Maryland camera yields a false zero.
        fairfax = bool(operator and "fairfax" in operator.lower())
        near_dc = in_dc(lat, lng)
        cell = _cell(lat, lng)
        geo: dict = {}
        if census_key or fairfax or near_dc:
            if cell in geo_cache:
                geo = geo_cache[cell]
            else:
                try:
                    geo = census_geographies(lat, lng)
                except requests.RequestException as exc:
                    print(f"camera {camera_id}: geocoder failed ({exc})", file=sys.stderr)
                geo_cache[cell] = geo
                time.sleep(PAUSE_S)

        try:
            # State FIPS 11 is the District itself.
            if near_dc and geo.get("state") == "11":
                if cell in dc_count_cache:
                    crime_count = dc_count_cache[cell]
                else:
                    crime_count = dc_incident_count(lat, lng)
                    dc_count_cache[cell] = crime_count
                    time.sleep(PAUSE_S)
                # 800 m is just under half a mile; the app speaks miles.
                crime_desc = (
                    "reported incidents within half a mile in the last "
                    "12 months (DC MPD)"
                )
            elif fairfax and geo.get("zip"):
                if fairfax_zip_counts is None:
                    fairfax_zip_counts, fairfax_week = fairfax_weekly_by_zip()
                crime_count = fairfax_zip_counts.get(geo["zip"], 0)
                crime_desc = (
                    f"reported incidents in ZIP {geo['zip']} in Fairfax "
                    f"County PD's weekly report ({fairfax_week})"
                )
        except requests.RequestException as exc:
            print(f"camera {camera_id}: crime lookup failed ({exc})", file=sys.stderr)

        if census_key and geo.get("state") and geo.get("county"):
            try:
                tract_key = (geo["state"], geo["county"], geo.get("tract") or "")
                if tract_key not in tract_income_cache:
                    tract_income_cache[tract_key] = acs_median_income(
                        geo["state"], geo["county"], geo.get("tract"), census_key
                    )
                    time.sleep(PAUSE_S)
                tract_income = tract_income_cache[tract_key]
                county_key = (geo["state"], geo["county"])
                if county_key not in county_income_cache:
                    county_income_cache[county_key] = acs_median_income(
                        geo["state"], geo["county"], None, census_key
                    )
                    time.sleep(PAUSE_S)
                county_income = county_income_cache[county_key]
            except requests.RequestException as exc:
                print(f"camera {camera_id}: ACS failed ({exc})", file=sys.stderr)

        if crime_count is None and tract_income is None:
            continue

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    UPDATE_SQL,
                    (crime_count, crime_desc, tract_income, county_income, camera_id),
                )
        updated += 1
        if updated % 25 == 0:
            print(f"{updated} cameras enriched", file=sys.stderr)

    return updated


# --------------------------------------------------------------------------
# Arrests, by police service area. Two API calls for the whole city: one
# grouped count per PSA, one fetch of the PSA polygons; every camera
# inside a polygon inherits its area's number locally.
# --------------------------------------------------------------------------

DC_PSA_URL = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
    "Public_Safety_WebMercator/MapServer/10/query"
)
DC_ARRESTS_URL = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
    "Public_Safety_WebMercator/MapServer/38/query"
)
ARREST_YEAR = 2025


def dc_arrests_by_psa() -> dict[int, int]:
    """{PSA number: arrests recorded in ARREST_YEAR}. One API call."""
    response = requests.get(
        DC_ARRESTS_URL,
        params={
            "where": f"YEAR = {ARREST_YEAR}",
            "groupByFieldsForStatistics": "DEFENDANT_PSA",
            "outStatistics": (
                '[{"statisticType":"count","onStatisticField":"OBJECTID",'
                '"outStatisticFieldName":"n"}]'
            ),
            "f": "json",
        },
        headers=HEADERS,
        timeout=120,
    )
    response.raise_for_status()
    counts: dict[int, int] = {}
    for feature in response.json().get("features", []):
        attrs = feature["attributes"]
        psa = attrs.get("DEFENDANT_PSA")
        # ArcGIS upper-cases the statistic field name on the way out.
        n = attrs.get("n", attrs.get("N"))
        try:
            counts[int(psa)] = int(n)
        except (TypeError, ValueError):
            continue
    return counts


def dc_psa_polygons() -> list[tuple[int, object]]:
    """[(PSA number, shapely polygon in WGS84)]. One API call."""
    from shapely.geometry import shape

    response = requests.get(
        DC_PSA_URL,
        params={
            "where": "1=1",
            "outFields": "PSA",
            "outSR": "4326",
            "f": "geojson",
        },
        headers=HEADERS,
        timeout=120,
    )
    response.raise_for_status()
    polygons = []
    for feature in response.json().get("features", []):
        psa = feature.get("properties", {}).get("PSA")
        try:
            polygons.append((int(psa), shape(feature["geometry"])))
        except (TypeError, ValueError):
            continue
    return polygons


def arrests_pass(database_url: str) -> int:
    """Fill arrest_count for every camera inside a DC police service area."""
    from shapely.geometry import Point

    import psycopg

    try:
        counts = dc_arrests_by_psa()
        polygons = dc_psa_polygons()
    except requests.RequestException as exc:
        print(f"arrest data unavailable ({exc})", file=sys.stderr)
        return 0

    updated = 0
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ST_Y(geom), ST_X(geom) FROM cameras "
                "WHERE active AND arrest_count IS NULL"
            )
            rows = cur.fetchall()
        with conn.cursor() as cur:
            for camera_id, lat, lng in rows:
                if not in_dc(lat, lng):
                    continue
                point = Point(lng, lat)
                psa = next(
                    (n for n, poly in polygons if poly.contains(point)), None
                )
                if psa is None or psa not in counts:
                    continue
                cur.execute(
                    "UPDATE cameras SET arrest_count = %s, arrest_desc = %s "
                    "WHERE id = %s",
                    (
                        counts[psa],
                        f"arrests recorded in police service area {psa} "
                        f"in {ARREST_YEAR} (DC MPD)",
                        camera_id,
                    ),
                )
                updated += 1
    return updated


# --------------------------------------------------------------------------
# The usefulness score. Deterministic and reproducible: crime percentile
# among cameras with crime data (50 pts), arrest percentile among cameras
# with arrest data (30 pts), and an income term (20 pts) that erodes as
# the neighborhood diverges from its county median - divergence is the
# placement-pattern signal, in either direction. Missing factors shrink
# the pool and the score is rescaled over what was measurable, with
# score_desc saying how many of the three factors were used.
# --------------------------------------------------------------------------


def _percentile(value: int, population: list[int]) -> float:
    """Fraction of the population at or below value, 0..1."""
    if not population:
        return 0.0
    return sum(1 for v in population if v <= value) / len(population)


def score_pass(database_url: str) -> int:
    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, crime_count, arrest_count, tract_income, "
                "county_income FROM cameras WHERE active"
            )
            rows = cur.fetchall()

    crime_pop = [r[1] for r in rows if r[1] is not None]
    arrest_pop = [r[2] for r in rows if r[2] is not None]

    updated = 0
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for camera_id, crime, arrests, tract, county in rows:
                earned = 0.0
                pool = 0.0
                used = 0
                if crime is not None:
                    earned += _percentile(crime, crime_pop) * 50
                    pool += 50
                    used += 1
                if arrests is not None:
                    earned += _percentile(arrests, arrest_pop) * 30
                    pool += 30
                    used += 1
                if tract is not None and county:
                    divergence = abs(tract - county) / county
                    earned += max(0.0, 1 - divergence / 0.5) * 20
                    pool += 20
                    used += 1

                # Income alone must not produce a number: an average
                # neighborhood would score a camera "useful" with zero
                # evidence of enforcement need. A numeric score requires
                # crime or arrest data.
                if crime is None and arrests is None:
                    score = None
                    desc = (
                        "insufficient public data (income only, 1 of 3 factors)"
                        if pool > 0
                        else "insufficient public data (0 of 3 factors)"
                    )
                else:
                    score = round(earned / pool * 100)
                    desc = f"scored on {used} of 3 factors"
                cur.execute(
                    "UPDATE cameras SET usefulness_score = %s, "
                    "score_desc = %s WHERE id = %s",
                    (score, desc, camera_id),
                )
                updated += 1
    return updated


def main(argv=None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL", "")
    )
    parser.add_argument("--limit", type=int, help="stop after this many updates")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("no DATABASE_URL; nothing to enrich", file=sys.stderr)
        return 1

    census_key = os.environ.get("CENSUS_API_KEY", "")
    if not census_key:
        print("CENSUS_API_KEY unset; skipping income", file=sys.stderr)

    updated = enrich(args.database_url, census_key, args.limit)
    print(f"enriched {updated} cameras")
    arrested = arrests_pass(args.database_url)
    print(f"arrest counts on {arrested} cameras")
    scored = score_pass(args.database_url)
    print(f"scored {scored} cameras")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
