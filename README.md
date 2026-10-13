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

## Docker

Build and run with Docker using the `.env` file. The image listens on port 8080. Run `alembic upgrade head` as a release step before starting a new deployment; the app does not mutate the schema at startup.

## Current scope

Inventory is shared across a movie's listed showtimes. A production ticketing system should model dated shows and allocate capacity per show (or per seat), then add expiring holds and payment confirmation. This app does not process payments.

## Development

Run `python -m pytest` for the API and booking regression tests. Keep schema changes in Alembic migrations and test fresh database setup before deploying.
