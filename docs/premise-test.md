# The premise test

The whole project rests on one assumption nobody has checked: that a
Google Maps deep link with waypoints actually holds the route Google
drives, rather than Google quietly optimising back onto the fast road.
If it does not hold, the waypoint picker and the avoidance routing are
both pointless and the design needs rethinking before anything else is
built.

This is a manual test. It needs a phone with Google Maps, two taps, and
about a minute. Nothing else in the repo can substitute for it.

## The links

Both corridors below are real Fairfax roads carrying a real ALPR camera
pulled from OSM via Overpass on 2026-08-21. The detour street is a real
parallel road roughly 400-500 m off the corridor. Coordinates are the
camera's OSM position, not an approximation.

### Case 1 - Fairfax Boulevard, ALPR at 38.859788,-77.302918

Detour street: Chain Bridge Road, 515 m off the corridor.

A. Baseline, no waypoints. Should run straight down Fairfax Boulevard,
   past the camera.

    https://www.google.com/maps/dir/?api=1&origin=38.853999%2C-77.318748&destination=38.864420%2C-77.277596&travelmode=driving

B. Same trip, one waypoint on Chain Bridge Road.

    https://www.google.com/maps/dir/?api=1&origin=38.853999%2C-77.318748&destination=38.864420%2C-77.277596&travelmode=driving&waypoints=38.863101%2C-77.307068

### Case 2 - Main Street, ALPR at 38.845315,-77.301790

Detour street: Locust Lane, 395 m off the corridor.

A. Baseline.

    https://www.google.com/maps/dir/?api=1&origin=38.851791%2C-77.321803&destination=38.841792%2C-77.275878&travelmode=driving

B. With one waypoint on Locust Lane.

    https://www.google.com/maps/dir/?api=1&origin=38.851791%2C-77.321803&destination=38.841792%2C-77.275878&travelmode=driving&waypoints=38.842327%2C-77.299337

## What to look for

1. Does B route differently from A at all? If the two look identical,
   Google dropped the waypoint and the premise fails outright.

   yea
2. Does B keep the detour after you press Start? A link can preview
   correctly and then be discarded once navigation begins.
3. Does B survive a reroute? Miss a turn deliberately, or let Google
   reroute for traffic, and see whether it returns to the waypoint or
   drops it and heads back to the fast road. The spec's drift detection
   assumes it can be dropped, which is why `/replan` exists - this
   confirms how often that path will actually be needed.
4. Does the waypoint show as a stop the driver has to acknowledge? If
   Google treats it as a destination rather than a pass-through, the
   driving experience changes and the app has to say so.

## Result

**Passes.** And confirmed again end to end on 2026-08-21 with the real
app: a plan built from live cameras opened in Google Maps carrying its
waypoint, and Google routed through it. Confirmed by khalid on 2026-08-21, tapping both cases on an
Android phone. The waypoint links route differently from the baseline and
hold the detour. The project's core premise is sound: Google Maps accepts
a deep link with waypoints and drives the route we hand it.

Checks 1 and 2 above are answered. Checks 3 and 4 are not, and cannot be
answered by tapping a link:

- **Reroute survival is assumed, not measured.** khalid's call, 2026-08-21:
  Google keeps the waypoints through a recalculation. That is consistent
  with deep link waypoints being stops rather than routing hints - a
  reroute recalculates the path to the current stop rather than skipping
  it. Re-planning is therefore built as a rare fallback, not as the main
  loop.

  Worth knowing which way this was decided, because if it turns out
  wrong the failure is silent: the plan screen would keep reporting
  cameras as avoided while the driver passes them. A drive down one of
  these corridors, missing a turn on purpose, still settles it cheaply.
- **Waypoints do present as stops. Confirmed 2026-08-21** on a real
  handover, Fairfax to Tysons Corner Center. Google Maps opened with a
  three-row stop list: the origin, then `Towers Crescent, Fashion Blvd`,
  then the destination. That middle row is our waypoint, a point on a
  road chosen to hold a detour, listed as somewhere the driver is going.

  It is not fatal - the route was correct and one minute slower - but it
  scales badly. The picker allows up to nine waypoints, which would be
  nine phantom stops on a road nobody is stopping at. Real trips have
  needed 0 to 4.

  Two things follow. The picker should prefer the fewest waypoints that
  hold the detour rather than the most robust set, and `MAX_WAYPOINTS`
  should probably come down from 9 once someone has seen how Google
  narrates several of them at speed. Whether it also announces an arrival
  at each one is still unknown and needs the car.
all woorks 
