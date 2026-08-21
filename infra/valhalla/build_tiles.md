# Building Valhalla routing tiles

The road graph Valhalla routes on. Nothing to do with the camera
ingestion job: this is built rarely (roads change slowly), by hand, on a
machine with RAM to spare, and the resulting tarball is uploaded to the
server. The server never builds anything.

Build it anywhere except OneDrive. The intermediate files are large and
syncing them is pointless.

## Build

Two stages: clip and merge the extracts yourself, then hand Valhalla one
file. Do not point `tile_urls` at the three state files - that is the
path the next section measures at over 55 minutes without finishing.

On Windows use PowerShell and put each `docker run` on a single line.
PowerShell's line continuation is a backtick, not a backslash; a pasted
backslash gives `docker: invalid reference format`. In Git Bash, prefix
commands with `MSYS_NO_PATHCONV=1` or it rewrites container paths like
`/data` into `C:/Program Files/Git/data`.

### 1. Download

    New-Item -ItemType Directory -Force C:alhalla\dmv\src, C:alhalla\dmv\custom_files
    cd C:alhalla\dmv\src
    curl.exe -L -O https://download.geofabrik.de/north-america/us/district-of-columbia-latest.osm.pbf
    curl.exe -L -O https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf
    curl.exe -L -O https://download.geofabrik.de/north-america/us/virginia-latest.osm.pbf

### 2. Clip to the region, then merge

The bounding box is `REGIONS["dmv"]` from `ingestion/ingestion/overpass.py`,
so the road graph covers the same ground the camera job ingests. osmium
takes it as left,bottom,right,top:

    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium extract -b -79.50,37.85,-75.05,39.75 -o /data/clip-dc.pbf /data/district-of-columbia-latest.osm.pbf --overwrite
    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium extract -b -79.50,37.85,-75.05,39.75 -o /data/clip-md.pbf /data/maryland-latest.osm.pbf --overwrite
    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium extract -b -79.50,37.85,-75.05,39.75 -o /data/clip-va.pbf /data/virginia-latest.osm.pbf --overwrite
    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium merge /data/clip-dc.pbf /data/clip-md.pbf /data/clip-va.pbf -o /data/dmv.pbf --overwrite

Measured: Virginia 407 MB clips to 136 MB, Maryland and DC are already
inside the box, and the merge lands at 358 MB. The clip and merge together
take well under a minute.

Copy the one merged file into `custom_files`, and make sure nothing else
`.pbf` is in there - the container builds from everything it finds:

    Copy-Item C:alhalla\dmv\src\dmv.pbf C:alhalla\dmv\custom_files
### 3. Build the tiles

No `tile_urls`: the container builds from the `.pbf` already present.

    docker run -dt --name valhalla-dmv -p 8003:8002 -v C:/valhalla/dmv/custom_files:/custom_files -e build_elevation=False -e build_admins=True -e build_time_zones=True -e force_rebuild=False -e serve_tiles=True ghcr.io/nilsnolde/docker-valhalla/valhalla:latest

Watch it with `docker logs -f valhalla-dmv`. It is done when
`curl localhost:8003/status` answers. The output is
`custom_files/valhalla_tiles.tar`; that single file is what ships to the
server.

`build_elevation=False` matters. Elevation data is enormous and this
project does not use it.

`admin_data/` and `timezone_data/` in `custom_files` are world-wide
downloads, about 123 MB together, and do not change with the region. Keep
them across rebuilds; delete everything else if you need a clean start.

### If a build went wrong

A build fed the unclipped state files does not fail, it just grinds - the
symptom is `valhalla_tiles/` climbing past a gigabyte while
`Adding complex turn restrictions` sits there. Stop it and clear the
partial output before rebuilding, or the container reuses it:

    docker stop valhalla-dmv; docker rm valhalla-dmv
    Remove-Item -Recurse -Force C:alhalla\dmv\custom_filesalhalla_tiles
    Remove-Item -Force C:alhalla\dmv\custom_filesile_hashes.txt, C:alhalla\dmv\custom_filesalhalla.json

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
