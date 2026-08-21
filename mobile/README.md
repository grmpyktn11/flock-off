# Mobile app

React Native (Expo) app shell for the camera-avoiding navigation project.
See `final-spec.md` for the full system design.

## What is here

- Search screen: Places-style autocomplete for start and destination.
- Plan screen: avoided camera count, ETA delta, unavoidable camera list,
  and a "Start in Google Maps" button.
- Deep link launch: hands the planned route to Google Maps.

The backend does not exist yet, so `src/api/mockBackend.ts` fakes the
`GET /search` and `POST /plan` responses with Fairfax / Herndon data.
Swapping in the real service means replacing that one file; the response
shapes in `src/api/types.ts` are the contract.

## Run

    npm install
    npm run android
