# Building Valhalla routing tiles

The road graph Valhalla routes on. Nothing to do with the camera
ingestion job: this is built rarely (roads change slowly), by hand, on a
machine with RAM to spare, and the resulting tarball is uploaded to the
server. The server never builds anything.

Build it anywhere except OneDrive. The intermediate files are large and
syncing them is pointless.

## Build

    python infra/valhalla/build_tiles.py --region dmv --work C:/valhalla

Downloads the region's extracts, clips each to its bounding box, merges
them, and starts the container. Region geography comes from
`regions.json`; see [../../docs/adding-a-region.md](../../docs/adding-a-region.md).

Watch it with `docker logs -f valhalla-dmv`. It is done when
`curl localhost:8003/status` answers. The output is
`custom_files/valhalla_tiles.tar`; that single file is what ships to the
server.

Do not point `--work` inside OneDrive. The intermediate files are large
and syncing them is pointless.

`build_elevation=False` matters. Elevation data is enormous and this
project does not use it.

`admin_data/` and `timezone_data/` in `custom_files` are world-wide
downloads, about 123 MB together, and do not change with the region. Keep
them across rebuilds; delete everything else if you need a clean start.

### If a build went wrong

A build fed unclipped state files does not fail, it just grinds - the
symptom is `valhalla_tiles/` climbing past a gigabyte while
`Adding complex turn restrictions` sits there. Stop it and clear the
partial output before rebuilding, or the container reuses it:

    docker stop valhalla-dmv; docker rm valhalla-dmv
    Remove-Item -Recurse -Force C:/valhalla/dmv/custom_files/valhalla_tiles
    Remove-Item -Force C:/valhalla/dmv/custom_files/file_hashes.txt, C:/valhalla/dmv/custom_files/valhalla.json

### Doing it by hand

The script runs these; they are here for when something needs unpicking.
In Git Bash prefix each with `MSYS_NO_PATHCONV=1`, or it rewrites `/data`
into `C:/Program Files/Git/data`. In PowerShell keep each on one line -
its continuation character is a backtick, not a backslash.

    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium extract -b -79.50,37.85,-75.05,39.75 -o /data/clip-virginia.pbf /data/virginia-latest.osm.pbf --overwrite
    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium merge /data/clip-dc.pbf /data/clip-md.pbf /data/clip-va.pbf -o /data/merged.pbf --overwrite
    docker run -dt --name valhalla-dmv -p 8003:8002 -v C:/valhalla/dmv/custom_files:/custom_files -e build_elevation=False -e build_admins=True -e build_time_zones=True -e force_rebuild=False -e serve_tiles=True ghcr.io/nilsnolde/docker-valhalla/valhalla:latest

Measured on the DMV: Virginia 407 MB clips to 136 MB, the merge lands at
358 MB, and the build takes 11 minutes on 12 threads for a 595 MB tarball.

## Why clipping and merging is not optional

The same region, built both ways on a 12-core machine:

| | 3 state files, unclipped | clipped + merged |
|---|---|---|
| input | 630.6 MiB | 357.4 MiB |
| build time | over 55 min, never finished | **10 min** |
| level 2 tiles | 288 | 150 |
| tiles out | 911 MB and climbing | **594 MB** |

Valhalla warns about multi-extract builds and the warning is worth
heeding. Overlapping state files duplicate ways along the borders, and
`Adding complex turn restrictions` -- which is single threaded, so extra
cores do not help -- ground on those duplicates for the best part of an
hour. The merged file cleared the same stage in seconds. `osmium merge`
deduplicates by object id, which is what makes the difference.

## Measured

Washington DC alone, as a smoke test of the toolchain:

| | |
|---|---|
| extract | 20 MB |
| tiles out | 34.7 MB (5 files) |
| build time | ~190s including downloads |
| fixed cost | timezones.sqlite 114 MB, admins.sqlite 6.7 MB |

The timezone and admin databases are world-wide and do not grow with the
region.

## Deploy

Copy `valhalla_tiles.tar` to the server and point a container at it with
`force_rebuild=False` and no `tile_urls`. It memory-maps the tarball and
starts serving in seconds.

## Verifying a build

`infra/valhalla/smoke_test.py` routes across the region, drops a real dead zone
from `ingestion.deadzone` onto that route, re-routes with
`exclude_polygons`, and asserts the first route crosses the polygon and
the second does not.
