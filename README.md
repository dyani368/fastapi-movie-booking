# Movie Booking

A server-rendered movie catalog and booking app with a JSON API, FastAPI, SQLAlchemy, PostgreSQL, Alembic, and Jinja templates. Users can register, sign in, browse movies, and reserve seats; admins manage the catalog.

## Run locally

1. Create a PostgreSQL database and copy `.env.example` to `.env`. Set `DATABASE_URL` and a long random `SECRET_KEY`. Set `SECURE_COOKIES=true` when serving over HTTPS.
2. Install dependencies with `python -m pip install -r requirements-dev.txt`.
3. Create the database schema with `alembic upgrade head`.
4. Start the app with `fastapi dev app/main.py`.

The web UI is at `/`; the interactive API documentation is at `/docs`; `/health` checks database connectivity. The first registered account is a regular user. Set `is_admin` for a trusted account directly in the database to grant catalog access; public registration never accepts a role.

## API outline

- `GET /api/movies` and `GET /api/movies/{id}` are public.
- `POST /api/movies` and `PATCH` or `DELETE /api/movies/{id}` require an admin bearer token.
- `POST /api/users` creates an account; `POST /api/users/token` returns a bearer token.
- `GET /api/bookings` returns the signed-in user's bookings (admins can review all); `POST /api/bookings` creates a booking for the signed-in user; `DELETE /api/bookings/{id}` cancels an owned booking or an admin cancellation.

Booking requests validate positive seat counts and lock the movie row while checking and updating inventory. This prevents concurrent overselling on PostgreSQL. Cookie-authenticated form submissions use a CSRF token; authentication cookies are HTTP-only and use `SameSite=Lax`.

## Booking SMS (Plivo)

Set `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, and `PLIVO_SOURCE_NUMBER` in the ignored `.env` file. Add an optional user phone number in E.164 format (for example `+14155552671`). After a booking commits, the app sends a best-effort confirmation; an SMS provider failure does not cancel the booking. Delivery state is available to the booking owner or an admin at `GET /api/bookings/{id}/sms-status`.

For delivery callbacks, set `PLIVO_STATUS_CALLBACK_URL` to the exact public HTTPS URL for `/webhooks/plivo/sms` (including any trailing slash). Expose the local app through a secure tunnel while testing, and configure that same URL in the app. The webhook validates Plivo's V2 signature, stores provider status updates, and acknowledges duplicate/stale callbacks. Do not commit `.env` or share the Auth Token. A Plivo trial may require the destination number to be verified in the Plivo console.

Run `python -m pytest` to exercise the sender and callback logic without sending real SMS. A live send requires active Plivo credentials and an SMS-capable source number.

## Docker

Build and run with Docker using the `.env` file. The image listens on port 8080. Run `alembic upgrade head` as a release step before starting a new deployment; the app does not mutate the schema at startup.

## Current scope

Inventory is shared across a movie's listed showtimes. A production ticketing system should model dated shows and allocate capacity per show (or per seat), then add expiring holds and payment confirmation. This app does not process payments.

## Development

Run `python -m pytest` for the API and booking regression tests. Keep schema changes in Alembic migrations and test fresh database setup before deploying.
