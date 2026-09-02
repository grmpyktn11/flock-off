# Privacy policy

**flock-off** &middot; last updated 2 September 2026

flock-off plans driving routes around license plate readers and speed
cameras, hands the route to Google Maps, and warns you about cameras the
route could not avoid. There is also a public website showing the camera
map and example trips.

## What we collect

Nothing that identifies you. No accounts, no sign-in, no email, no
advertising ID. Nothing links one trip to another.

The one identifier that exists: a token used solely to count how many
free AI camera notes a device has used. On Android it is a one-way hash
of the system's app-scoped device id (ANDROID_ID) - the id itself never
leaves your phone, the hash cannot be reversed to it, and since the id
is scoped to this app's signing key the token cannot be matched against
any other app's records. It is sent only with explanation requests and
stored only next to a counter.

## Your location

- **On your phone:** while a trip runs, the app reads GPS to warn you
  near cameras and notice if you left the route. This happens on the
  device. Positions are never transmitted.
- **Sent to our server:** planning a route sends an origin and a
  destination. Nothing else.
- **Not stored:** the server does not write route requests to disk, and
  its request access log is turned off, so search text and addresses
  never land in a log file either. It keeps per-IP request counts for
  abuse detection; they contain no coordinates and are discarded on
  restart.
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
- **Anthropic (Claude)** writes the short "why is this camera here"
  notes, once per camera, from public facts about the camera - never
  from anything about you or your trip. If you add your own Anthropic
  API key in settings, it is stored only on your phone, sent only to our
  server with explanation requests, used for that one batch, and never
  stored or logged server-side; Anthropic's use of it is covered by
  [Anthropic's privacy policy](https://www.anthropic.com/legal/privacy).

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
