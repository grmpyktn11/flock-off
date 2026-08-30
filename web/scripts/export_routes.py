"""Precompute the showcase route comparisons to static JSON.

Runs the real planning pipeline for a few demo trips and writes
web/public/data/routes.json with both geometries: the route Google would
drive anyway, and the one that dodges the readers. The planner computes
the baseline internally but does not return its shape, so this wraps
google.directions and keeps the no-waypoint answer; the demo costs no
Google calls beyond what /plan itself makes.

Needs the works: DATABASE_URL, VALHALLA_URL (container up), and
GOOGLE_API_KEY in the repo root .env.

    python web/scripts/export_routes.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app import cameras as camera_source  # noqa: E402
from app import config, google, planner  # noqa: E402
from app.geo import encode_polyline  # noqa: E402

OUT = REPO / "web" / "public" / "data" / "routes.json"

# Probed against the live pipeline; each tells a different true story
# about density and what escaping it costs. GMU-Tysons runs a gauntlet of
# seven readers - campus, county and the mall's own - and dodges six for
# 1.7 minutes. Oakton-GMU pays 3.8 minutes on an 11-minute drive and the
# campus readers still catch it at the gate. Falls Church-Fairfax clears
# all six cameras on Google's route for 1.8 minutes.
TRIPS = [
    ("George Mason University", (38.8290, -77.3050),
     "Tysons Corner Center", (38.9180, -77.2225)),
    ("Oakton", (38.8810, -77.3008),
     "George Mason University", (38.8290, -77.3050)),
    ("Falls Church", (38.8823, -77.1711), "Fairfax City", (38.8462, -77.3064)),
]


def main() -> None:
    for flag, name in [
        (config.USE_MOCK_CAMERAS, "DATABASE_URL"),
        (config.USE_MOCK_ROUTING, "VALHALLA_URL"),
        (config.USE_MOCK_GOOGLE, "GOOGLE_API_KEY"),
    ]:
        if flag:
            sys.exit(f"{name} is not set; the showcase data must be real")

    demos = []
    for origin_name, origin, destination_name, destination, in TRIPS:
        baseline: dict = {}
        real_directions = google.directions

        def capturing(o, waypoints, d):
            route, eta = real_directions(o, waypoints, d)
            if not waypoints and not baseline:
                baseline["route"] = route
                baseline["polyline"] = encode_polyline(route)
            return route, eta

        google.directions = capturing
        try:
            plan = planner.plan_route(origin, destination)
        finally:
            google.directions = real_directions

        # Which of the reported cameras sat on Google's route. The planner
        # calls everything on the driven route "unavoidable", but a camera
        # the detour newly drives past was never unavoidable - it is the
        # detour's own cost, and the page must not claim it was always
        # there. Every avoided camera is on the baseline by definition;
        # this flag separates the in-view ones.
        bbox_cameras = camera_source.in_bbox(origin, destination)
        baseline_ids = camera_source.seen_by(baseline["route"], bbox_cameras)

        print(f"{origin_name} -> {destination_name}: "
              f"avoided {plan.avoided_count}, unavoidable {plan.unavoidable_count}, "
              f"delta {plan.eta_delta_seconds}s")

        demos.append({
            "origin": {"name": origin_name, "lat": origin[0], "lng": origin[1]},
            "destination": {
                "name": destination_name, "lat": destination[0], "lng": destination[1],
            },
            "baseline_polyline": baseline["polyline"],
            "route_polyline": plan.route_polyline,
            "cameras": [
                {**c.model_dump(), "on_baseline": c.id in baseline_ids}
                for c in plan.cameras
            ],
            "avoided_count": plan.avoided_count,
            "unavoidable_count": plan.unavoidable_count,
            "baseline_eta_seconds": plan.baseline_eta_seconds,
            "route_eta_seconds": plan.route_eta_seconds,
            "eta_delta_seconds": plan.eta_delta_seconds,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"demos": demos}, indent=1))
    print(f"{len(demos)} demos -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
