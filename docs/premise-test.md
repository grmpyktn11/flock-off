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

**Passes.** Confirmed by khalid on 2026-08-21, tapping both cases on an
Android phone. The waypoint links route differently from the baseline and
hold the detour. The project's core premise is sound: Google Maps accepts
a deep link with waypoints and drives the route we hand it.

Checks 1 and 2 above are answered. Checks 3 and 4 are not, and cannot be
answered by tapping a link:

- **Reroute survival is still unknown.** Whether Google keeps the
  waypoint after a missed turn or a traffic reroute needs an actual
  drive down one of these corridors. This decides whether `/replan` is a
  rare fallback or the main event, so it is worth an hour in the car
  before the drive-time features are designed.
- **Whether the waypoint presents as a stop the driver must acknowledge**
  was not recorded. If Google treats it as a destination rather than a
  pass-through, the app has to warn the user about it.
all woorks 
