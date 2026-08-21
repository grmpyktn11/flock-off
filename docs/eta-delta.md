# The ETA delta is not measuring what the spec thinks

Measured 2026-08-21 against Valhalla 3.5.1 serving the DMV tiles, with
real dead zones from the live cameras table.

The spec's per-trip flow says:

> ETA honesty check: compare avoidance route ETA vs baseline, surface the
> delta to the user

That number is the one thing the app asks the user to accept - "this
detour costs you 7 minutes". It is currently not trustworthy, for two
separate reasons.

## 1. Valhalla's unconstrained route is not its best route

Eight Fairfax-area corridors, six of which carry a dead zone. Excluding
the dead zones produced a *faster* route than asking for the plain
fastest route on two of the six:

| trip | zones | baseline | avoidance | delta |
|---|---|---|---|---|
| 38.846,-77.306 -> 38.970,-77.386 | 2 | 21.11 km / 1204s | 19.79 km / 1205s | +2s |
| 38.861,-77.376 -> 38.918,-77.221 | 1 | 19.82 km / 922s | 20.30 km / 990s | +67s |
| 38.953,-77.457 -> 38.918,-77.221 | 5 | 29.50 km / 1738s | 29.19 km / 1869s | +131s |
| 38.846,-77.306 -> 38.953,-77.457 | 2 | 26.64 km / 1768s | 21.53 km / 1598s | **-171s** |
| 38.970,-77.386 -> 38.861,-77.376 | 1 | 16.04 km / 894s | 15.15 km / 883s | -11s |
| 38.878,-77.272 -> 38.959,-77.357 | 1 | 16.05 km / 991s | 24.50 km / 1033s | +42s |

Removing edges from a graph cannot make the true optimum better. So on
the -171s row, the baseline Valhalla returned is simply not the best
route Valhalla can find: it produced a 1598s route for the same origin
and destination when asked a harder question.

### It is not the exclusion mechanism itself

The obvious suspect - that passing `exclude_polygons` at all changes how
the search runs - is ruled out. On the -171s trip:

| what was excluded | result |
|---|---|
| nothing | 26.64 km / 1768s |
| the 2 real dead zones | 21.53 km / 1598s |
| a dummy square ~400m off the corridor, on no road | 26.64 km / 1768s |
| a dummy square in the Atlantic | 26.64 km / 1768s |

Both dummies are byte-identical to the baseline. An exclusion that
removes no edges changes nothing.

That leaves the hierarchy explanation, which the ingestion handoff
guessed at: Valhalla routes long trips on higher hierarchy levels using
shortcut edges, and a shortcut containing an excluded edge cannot be
used, so the search drops to a finer level near the exclusion and
explores what the shortcuts were hiding. This is consistent with every
measurement above but has not been proven - proving it needs
`hierarchy_limits`, which is gated behind
`service_limits.allow_hierarchy_limits_modifications` in the server
config.

## 2. The spec compares two different engines anyway

Even with a perfect Valhalla baseline, the spec's comparison is Google's
traffic-aware ETA against Valhalla's traffic-free one. Those differ by
engine, by speed model, and by whether traffic exists. A delta built from
them mixes the cost of avoiding cameras with the gap between two
routing products.

## What was done

Implemented 2026-08-21. Both ETAs now come from `app/google.py`:

Get both ETAs from the same engine, and make it the engine that actually
drives the trip:

1. Valhalla picks the avoidance route. It is the only one that can, since
   it is the only one that takes `exclude_polygons`.
2. Ask Google for the plain route ETA, as now.
3. Ask Google for the ETA *of our avoidance route*, by pricing the deep
   link's waypoints.
4. The delta is Google minus Google: same engine, same traffic model, and
   it is the number the driver will actually experience, because Google
   is doing the navigating.

Valhalla's duration is no longer read anywhere. `_route_avoiding` returns
geometry only, which sidesteps finding 1 entirely: the suboptimal
baseline stops mattering because nothing shows it to anyone.

### Cost

One Routes call per plan, not two. The picker already routes its picks
through Google to check Google will follow them, and that response
carries the duration of exactly those picks, so the avoidance ETA is free
whenever validation passes first time. Only the baseline needs a call of
its own, and the spec always called for that.

The second call comes back when the picks are adjusted after the last
validation call, because then the duration on hand describes a set of
waypoints that no longer exists. Against the bundled mock that is every
trip: mock Google draws straight legs between waypoints, which no bowed
avoidance route matches, so validation always exhausts its adjustments.
Real Google follows roads, so the common case should be the cheap one -
worth confirming once the key is in, by counting calls on a few real
trips.

With no key configured the mock answers and the numbers are placeholders,
but the structure is right and one invariant is now testable and tested:
a trip with no waypoints has a delta of exactly zero, because both ETAs
price the same route. Under the old scheme that case could report a
non-zero delta purely from the engine mismatch.

## Reproducing

Valhalla must be serving the DMV tiles on port 8003 and `DATABASE_URL`
must point at the cameras table. `infra/valhalla/smoke_test.py` covers
the single-route case; the table above came from routing the eight pairs
with and without the dead zones their baseline crosses.
