# Tappr landing page

A responsive, mobile-first landing page for an NFC smart card startup.

## Run locally

```bash
python3 server.py
```

Then open `http://localhost:4173`.

The card management screen is available at `http://localhost:4173/admin`. It
can list, create, and edit local cards, including their destination and status.
This MVP admin screen does not have authentication, so do not expose it publicly.

## Test the NFC redirect

The app automatically creates a SQLite database at `data/tappr.db` the first
time `server.py` starts. It creates the `cards` and `tap_events` tables and seeds
`DEMO123` only when that card does not already exist. Cards and taps remain in
the database when the server restarts.

1. Start the server with `python3 server.py`.
2. Open `http://localhost:4173/t/DEMO123` in a browser.
3. You will be redirected to `https://www.google.com`. The persisted tap count is
   increased and a UTC tap event is recorded before the redirect.

You can inspect the redirect without following it by running:

```bash
curl -i http://localhost:4173/t/DEMO123
```

The response will have status `302` and a `Location: https://www.google.com`
header. Visiting an unknown card such as `http://localhost:4173/t/UNKNOWN` shows
a friendly error page instead.

Run the automated redirect and landing-page tests with:

```bash
python3 -m unittest -v
```

## Reset the local database

Stop the server, delete the SQLite file, and start the server again:

```bash
rm -f data/tappr.db data/tappr.db-shm data/tappr.db-wal
python3 server.py
```

The tables and a fresh `DEMO123` card will be created automatically. Do not use
this reset command if you need to keep your local card or tap data.
