# Deferred work

Things consciously not being built yet, and what would have to be true to
start them. Not a wishlist: everything here is in the spec.

## Re-planning after a missed turn

The spec's drift detection: every GPS tick, measure point-to-line distance
from the driver to the stored route polyline, and if it exceeds 100m for
three consecutive ticks, offer a one-tap re-plan through `POST /replan`.

`POST /replan` is already built and tested. It is a fresh plan from the
driver's current position - same cameras query, same exclusions, same
waypoint picker. The client half is what is missing.

**Why it is waiting.** The question that decides its shape is unanswered:
does Google keep the waypoints after a missed turn or a traffic reroute?
The deep link premise test confirmed Google accepts and holds waypoints
from a cold start, but says nothing about what happens once it starts
recalculating mid-drive. If Google drops them reliably, drift fires
constantly and re-planning stops being a rare fallback and becomes the
main loop - which is a different app, with different battery and data
costs and a much more intrusive feel.

**How to answer it.** Drive one of the corridors in
[premise-test.md](premise-test.md) with a waypoint link running, miss a
turn on purpose, and watch whether the route returns to the waypoint or
heads back to the fast road. An hour in the car settles it.

**Design note for whoever builds it.** Gate the prompt on
`avoided_count`. A re-plan from the current position that avoids zero
cameras means Google's path is already as good as anything we would
propose, so say nothing rather than interrupting the driver. The pipeline
computes that number already. Worth pairing with a cap on re-plans per
trip and a cooldown, so a driver weaving near the 100m threshold is not
prompted repeatedly.

## Trip end conditions

The spec ends the foreground service on arrival, manual stop, or a long
stationary period. Nothing to design here; it just follows whenever the
foreground service is built for the proximity alerts.
