# Privacy policy

**flock-off** &middot; last updated 30 August 2026

flock-off plans driving routes around license plate readers and speed
cameras, hands the route to Google Maps, and warns you about cameras the
route could not avoid. There is also a public website showing the camera
map and example trips.

## What we collect

Nothing that identifies you. No accounts, no sign-in, no email, no device
identifier, no advertising ID. Nothing links one trip to another.

## Your location

- **On your phone:** while a trip runs, the app reads GPS to warn you
  near cameras and notice if you left the route. This happens on the
  device. Positions are never transmitted.
- **Sent to our server:** planning a route sends an origin and a
  destination. Nothing else.
- **Not stored:** the server does not write route requests to disk. It
  keeps per-IP request counts for abuse detection; they contain no
  coordinates and are discarded on restart.
- **Background location:** optional. Grant it and warnings work while
  Google Maps is in front. Decline and planning still works; you lose
  the spoken warnings.

## Other services

- **Google Maps Platform** handles place search and route timings. Your
  search text and trip endpoints reach Google, covered by
  [Google's privacy policy](https://policies.google.com/privacy).
  Tapping through to navigate puts you in the Google Maps app.
- **OpenStreetMap** is where camera locations come from. Nothing about
  you is sent to it.

## On your device

The current trip (route, cameras, spoken warnings) is saved locally so it
survives an app restart. Overwritten by the next trip, removed on
uninstall, never leaves the device.

## Data we could hand over

No route history exists on the server, so there is nothing to disclose to
anyone. That is a consequence of the design, not a promise.

## The website

Static page. No accounts, analytics, tracking, or cookies.

- The locate button uses your position in-browser only, to move the map.
- Map tiles come from [OpenFreeMap](https://openfreemap.org/); your
  browser requests tiles for the area you view.
- Theme choice is stored in your browser.
- Camera data is a static file computed from public records.

## Children

flock-off is a driving aid and is not directed at children.

## Changes

Material changes will be published here with a new date.

## Contact

Open an issue on the project's repository.
