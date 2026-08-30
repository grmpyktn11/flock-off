# Why both ETAs come from Google

The ETA delta ("this detour costs you 7 minutes") is the one number the
app asks the driver to accept. Two findings made us change how it is
computed. Measured 2026-08-21 on live services.

## Findings

1. **Valhalla's baseline is not its best route.** On 2 of 6 measured
   trips, excluding dead zones produced a faster route than the plain
   fastest-route query (one trip: -171s). Removing edges cannot improve
   the true optimum, so the baseline itself was suboptimal. Likely a
   hierarchy/shortcut-edge artifact.
2. **Comparing engines mixes two error sources.** Google's traffic-aware
   ETA vs Valhalla's traffic-free one measures the gap between two
   routing products, not the cost of avoiding cameras. First live run
   reported +23 minutes to avoid two cameras, mostly engine disagreement.

## The fix

Both ETAs come from Google, the engine that actually drives the trip:

1. Valhalla picks the avoidance route (only it can exclude polygons).
2. Google prices the plain route.
3. Google prices our route via the deep link's waypoints.
4. Delta is Google minus Google.

Valhalla's duration is never read. The waypoint validation call already
returns Google's route and duration, so the usual trip costs one extra
Routes call, not two.

Cameras are also checked against Google's returned route, not Valhalla's.
The deep link hands Google waypoints and Google fills in the rest, so
Valhalla's geometry is not what gets driven (median deviation 1456m on
one trip). Checking the wrong route reported cameras avoided that the
driver drove straight past.

## Artifacts

- A trip with no waypoints has a delta of exactly zero (same route priced
  twice).
- The two pricing calls happen seconds apart, so traffic can move between
  them. A delta of -0.4 minutes is jitter, not a saving.
