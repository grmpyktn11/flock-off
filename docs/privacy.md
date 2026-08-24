# Privacy policy

**flock-off** &middot; last updated 21 August 2026

flock-off plans driving routes around automated licence plate readers and
fixed speed cameras, then hands the route to Google Maps. While you drive
it warns you about cameras the route could not avoid.

This policy describes every piece of data the app touches. It is short
because the app collects almost nothing, and that is deliberate: an app
whose purpose is to give you a choice about being recorded would be a poor
one if it kept a record of you.

## What we collect

**Nothing that identifies you.** There are no accounts, no sign-in, no
email address, no device identifier, and no advertising ID. Nothing links
one trip you plan to another.

## Your location

**On your phone.** While a trip is running, the app reads your GPS
position every couple of seconds so it can tell you when you are
approaching a camera and notice if you have left the planned route. That
processing happens entirely on the device. Those positions are never
transmitted anywhere.

**Sent to our server.** When you plan a route, the app sends the server a
starting point and a destination so it can work out a route. That request
carries nothing else - no account, no device, no history.

**Not stored.** Our server does not write route requests to disk. It keeps
counts of how many requests each network address made, so we can notice
somebody abusing the service, and those counts contain no coordinates and
are discarded when the server restarts.

**Background location.** If you grant it, the app keeps reading your
position after you switch to Google Maps, because the warnings are the
whole point and by design this app is not the one on your screen. You can
decline. If you do, route planning still works; you lose the spoken
warnings, and the app tells you so.

## Other services

Planning a route requires two outside services:

- **Google Maps Platform** provides place search and route timings. Your
  search text and the two endpoints of your trip reach Google as part of
  this. Google's handling of that data is covered by
  [Google's privacy policy](https://policies.google.com/privacy).
- **OpenStreetMap** is where camera locations come from. We read from it;
  nothing about you is sent to it.

When you tap through to navigate, you leave flock-off and enter the Google
Maps app, which is governed by Google's policy and not this one.

## What is stored on your device

The trip you are currently driving - its route, its camera list, and which
warnings have already been spoken - is saved to your phone's local storage
so a trip survives the app being closed or restarted. It is overwritten by
your next trip and removed when you uninstall the app. It never leaves the
device.

## Data we could hand over

Because no route history exists on our server, there is none to disclose -
to advertisers, to data brokers, or in response to a legal demand. This is
a consequence of the design rather than a promise about our conduct, which
is the stronger of the two.

## Children

flock-off is a driving aid and is not directed at children.

## Changes

Material changes to this policy will be published here with a new date at
the top.

## Contact

Questions about this policy: open an issue on the project's repository.
