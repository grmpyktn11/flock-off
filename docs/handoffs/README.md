# Handoff notes

Written at the end of the three parallel build sessions that produced the
first version of each piece, before any of them were integrated.

They are kept as a record of why things are the way they are, and they are
worth reading for that. They are **not** current: much of what they
describe as open has since been settled, and some of what they recommend
was tried and turned out wrong. Where they disagree with the code, the
code is right.

Specifically, since these were written:

- The waypoint picker was reported as never producing a waypoint. It
  works; the trip it was tried on had no camera near it.
- The ETA comparison they describe was rebuilt. See
  [../eta-delta.md](../eta-delta.md).
- Regions moved from `overpass.py` into `regions.json` at the repo root.
- The backend reads cameras from PostGIS and routes through Valhalla,
  rather than the mocks these describe.
