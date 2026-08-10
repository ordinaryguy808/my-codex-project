# Tappr Tap Devices

A responsive landing page, Tap Device admin, NFC redirect service, and
early-access customization request workflow.

## Run locally

```bash
python3 server.py
```

Then open `http://localhost:4173`.

The Tap Device management screen is available at `http://localhost:4173/admin`.
It can list, create, and edit NFC Cards, Review / Social Plaques, and Property
Sign Tags, including each device's destination and status. Customer requests
and private artwork downloads are managed on the same screen.
This MVP admin screen does not have authentication, so do not expose it publicly.

Visit `http://localhost:4173/customize` to test the customer request form. It
accepts PNG, JPG, JPEG, and PDF artwork up to 10 MB. Uploads are stored under
the private, gitignored `data/uploads/` directory and are never served as public
static files.

## Test the NFC redirect

The app automatically creates a SQLite database at `data/tappr.db` the first
time `server.py` starts. It creates the `cards`, `tap_events`, and
`customer_requests` tables and seeds
`DEMO123` only when that card does not already exist. Cards and taps remain in
the database when the server restarts. Existing databases are migrated in place
with a `product_type` column; all existing card records remain compatible and
default to `CARD`.

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
