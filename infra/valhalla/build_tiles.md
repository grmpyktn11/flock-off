# Building Valhalla routing tiles

The road graph Valhalla routes on. Built rarely, by hand, on your
machine. The server only receives the finished tarball.

## Build

    python infra/valhalla/build_tiles.py --region dmv --work C:/valhalla

Downloads the region's extracts, clips each to the bbox, merges them, and
starts the container. Watch with `docker logs -f valhalla-dmv`. Done when
`curl localhost:8003/status` answers. Output:
`custom_files/valhalla_tiles.tar`.

Rules:

- Do not point `--work` at OneDrive or any synced folder.
- `build_elevation=False`. Elevation data is huge and unused.
- Keep `admin_data/` and `timezone_data/` across rebuilds (~123 MB,
  region-independent). Delete everything else for a clean start.

DMV numbers: ~11 min build, 595 MB tarball, 1.5 GB RAM.

## If a build goes wrong

A build fed unclipped files grinds instead of failing: `valhalla_tiles/`
climbs past a gigabyte while `Adding complex turn restrictions` sits
there. Stop it and clear the partial output, or the container reuses it:

    docker stop valhalla-dmv; docker rm valhalla-dmv
    Remove-Item -Recurse -Force C:/valhalla/dmv/custom_files/valhalla_tiles
    Remove-Item -Force C:/valhalla/dmv/custom_files/file_hashes.txt, C:/valhalla/dmv/custom_files/valhalla.json

## Why clip and merge

Unclipped state files duplicate ways along borders, and the
single-threaded turn restriction stage grinds on them. Measured on the
DMV: unclipped never finished in 55 minutes; clipped and merged built in
10. `osmium merge` deduplicates by object id.

## By hand

The script runs these. In Git Bash prefix with `MSYS_NO_PATHCONV=1`; in
PowerShell keep each on one line.

    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium extract -b -79.50,37.85,-75.05,39.75 -o /data/clip-virginia.pbf /data/virginia-latest.osm.pbf --overwrite
    docker run --rm -v C:/valhalla/dmv/src:/data stefda/osmium-tool osmium merge /data/clip-dc.pbf /data/clip-md.pbf /data/clip-va.pbf -o /data/merged.pbf --overwrite
    docker run -dt --name valhalla-dmv -p 8003:8002 -v C:/valhalla/dmv/custom_files:/custom_files -e build_elevation=False -e build_admins=True -e build_time_zones=True -e force_rebuild=False -e serve_tiles=True ghcr.io/nilsnolde/docker-valhalla/valhalla:latest

## Deploy

Copy `valhalla_tiles.tar` to the server, run a container with
`force_rebuild=False` and no `tile_urls`. It memory-maps the tarball and
serves in seconds.

## Verify

    python infra/valhalla/smoke_test.py --port 8003 --from <lat,lng> --to <lat,lng>

Routes across the region, drops a real dead zone on the route, re-routes
with it excluded, asserts the first route crosses it and the second does
not.
