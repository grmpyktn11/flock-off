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

# Probed against the live pipeline; picked because a reader on a bridge
# gates everything behind it. The Bay Bridge carries four readers and is
# the only Chesapeake crossing for a hundred miles, so Cape St.
# Claire-Stevensville stays unseen only by driving around the bay: two
# and a quarter hours extra on a 20-minute trip. The Nice Bridge is the
# only Potomac crossing for forty, which prices La Plata-Dahlgren at an
# extra hour and a half and Waldorf-Colonial Beach at an extra hour, all
# three with every camera cleared.
TRIPS = [
    ("Cape St. Claire", (39.0430, -76.4520), "Stevensville", (38.9807, -76.3266)),
    ("La Plata", (38.5292, -76.9755), "Dahlgren", (38.3311, -77.0508)),
    ("Waldorf", (38.6246, -76.9391), "Colonial Beach", (38.2546, -76.9635)),
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
