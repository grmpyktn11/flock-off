# Building Valhalla routing tiles

The road graph Valhalla routes on. Nothing to do with the camera
ingestion job: this is built rarely (roads change slowly), by hand, on a
machine with RAM to spare, and the resulting tarball is uploaded to the
server. The server never builds anything.

Build it anywhere except OneDrive. The intermediate files are large and
syncing them is pointless.

## Build

    docker run -dt --name valhalla-dmv -p 8003:8002 \
      -v C:\valhalla\dmv\custom_files:/custom_files \
      -e tile_urls="https://download.geofabrik.de/north-america/us/district-of-columbia-latest.osm.pbf https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf https://download.geofabrik.de/north-america/us/virginia-latest.osm.pbf" \
      -e build_elevation=False \
      -e build_admins=True \
      -e build_time_zones=True \
      -e force_rebuild=False \
      ghcr.io/nilsnolde/docker-valhalla/valhalla:latest

Watch it with `docker logs -f valhalla-dmv`. It is done when
`curl localhost:8003/status` answers. The output is
`custom_files/valhalla_tiles.tar`; that single file is what ships to the
server.

`build_elevation=False` matters. Elevation data is enormous and this
project does not use it.

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
