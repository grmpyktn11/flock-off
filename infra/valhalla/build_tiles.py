"""Build Valhalla routing tiles for a region.

    python infra/valhalla/build_tiles.py --region dmv --work C:/valhalla

Downloads the region's OSM extracts, clips each to the region bounding
box, merges them into one file, and starts the Valhalla container to
build tiles from it. Everything comes from regions.json, so a new city
needs no changes here.

The clip and merge are not optional. Feeding Valhalla several unclipped
state extracts leaves duplicate ways along the shared borders, and the
single-threaded turn restriction stage grinds on them: measured at over
55 minutes without finishing, against 11 minutes for the merged file.

Needs Docker. Do not put the work directory inside a synced folder like
OneDrive; the intermediate files are large and syncing them is pointless.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ingestion"))

from ingestion import regions  # noqa: E402

OSMIUM_IMAGE = "stefda/osmium-tool"
VALHALLA_IMAGE = "ghcr.io/nilsnolde/docker-valhalla/valhalla:latest"


def run(command: list[str]) -> None:
    print("  $", " ".join(command), flush=True)
    # MSYS_NO_PATHCONV stops Git Bash on Windows rewriting a container
    # path like /data into C:/Program Files/Git/data.
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    subprocess.run(command, check=True, env=env)


def osmium(work: Path, *args: str) -> None:
    run(["docker", "run", "--rm", "-v", f"{work.as_posix()}:/data", OSMIUM_IMAGE, "osmium", *args])


def download(urls: list[str], into: Path) -> list[Path]:
    paths = []
    for url in urls:
        target = into / url.rsplit("/", 1)[-1]
        if target.exists():
            print(f"  have {target.name}")
        else:
            print(f"  downloading {target.name}", flush=True)
            urlretrieve(url, target)
        paths.append(target)
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="dmv", choices=regions.names())
    parser.add_argument(
        "--work",
        default="C:/valhalla" if os.name == "nt" else str(Path.home() / "valhalla"),
        help="scratch directory, not inside OneDrive or any synced folder",
    )
    parser.add_argument("--container", default=None, help="defaults to valhalla-<region>")
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args(argv)

    extracts = regions.osm_extracts(args.region)
    if not extracts:
        parser.error(
            f"regions.json lists no osm_extracts for {args.region!r}, so there is"
            " nothing to build tiles from. Add the Geofabrik downloads its"
            " bounding box touches."
        )

    work = Path(args.work) / args.region
    src, custom = work / "src", work / "custom_files"
    src.mkdir(parents=True, exist_ok=True)
    custom.mkdir(parents=True, exist_ok=True)
    container = args.container or f"valhalla-{args.region}"

    print(f"1. downloading {len(extracts)} extract(s) into {src}")
    downloaded = download(extracts, src)

    print(f"2. clipping to {args.region} and merging")
    box = regions.osmium_bbox(args.region)
    clipped = []
    for path in downloaded:
        out = f"clip-{path.name}"
        osmium("extract", "-b", box, "-o", f"/data/{out}", f"/data/{path.name}", "--overwrite")
        clipped.append(out)
    osmium("merge", *[f"/data/{c}" for c in clipped], "-o", "/data/merged.pbf", "--overwrite")

    # The container builds from every .pbf it finds, so the merged file
    # has to arrive alone.
    for stale in custom.glob("*.pbf"):
        stale.unlink()
    (custom / f"{args.region}.pbf").write_bytes((src / "merged.pbf").read_bytes())

    print(f"3. building tiles in container {container}")
    run([
        "docker", "run", "-dt", "--name", container,
        "-p", f"{args.port}:8002",
        "-v", f"{custom.as_posix()}:/custom_files",
        "-e", "build_elevation=False",
        "-e", "build_admins=True",
        "-e", "build_time_zones=True",
        "-e", "force_rebuild=False",
        "-e", "serve_tiles=True",
        VALHALLA_IMAGE,
    ])

    print(f"\nBuilding. Watch it with:   docker logs -f {container}")
    print(f"Done when this answers:    curl localhost:{args.port}/status")
    print(f"Ships to the server as:    {custom / 'valhalla_tiles.tar'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
