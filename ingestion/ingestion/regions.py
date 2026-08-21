"""Region definitions, loaded from regions.json at the repo root.

One file so the camera ingestion and the Valhalla tile build agree about
where a region is. See docs/adding-a-region.md.
"""

import json
from pathlib import Path

REGIONS_FILE = Path(__file__).resolve().parents[2] / "regions.json"


def _load() -> dict:
    data = json.loads(REGIONS_FILE.read_text())
    return {name: spec for name, spec in data.items() if not name.startswith("_")}


REGIONS_SPEC = _load()

# Name to (south, west, north, east), the order Overpass expects.
REGIONS = {name: tuple(spec["bbox"]) for name, spec in REGIONS_SPEC.items()}


def names() -> list[str]:
    return sorted(REGIONS)


def bbox(region: str) -> tuple[float, float, float, float]:
    return REGIONS[region]


def osmium_bbox(region: str) -> str:
    """The same box as osmium wants it: left,bottom,right,top."""
    south, west, north, east = REGIONS[region]
    return f"{west},{south},{east},{north}"


def osm_extracts(region: str) -> list[str]:
    return list(REGIONS_SPEC[region].get("osm_extracts", []))


def description(region: str) -> str:
    return REGIONS_SPEC[region].get("description", "")
