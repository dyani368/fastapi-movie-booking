# Cinebook

Cinebook is a small full-stack movie ticket booking demo. A React and TypeScript interface talks to a FastAPI API backed by PostgreSQL. It includes a movie catalog, dated screenings, a temporary ticket hold, Razorpay test checkout, and optional Google Calendar events for confirmed bookings.

## Run locally

1. Create a PostgreSQL database and copy `.env.example` to `.env`. Set `DATABASE_URL` and a long random `SECRET_KEY`.
2. Install Python packages with `python -m pip install -r requirements-dev.txt`.
3. Apply migrations with `alembic upgrade head`.
4. Add demo films and future screenings with `python scripts/seed_demo.py`.
5. Start FastAPI with `fastapi dev app/main.py`.
6. In another terminal, run `cd frontend`, `npm install`, and `npm run dev`.

Open the Vite URL, usually `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

To serve the built React app through FastAPI, build `frontend` with `npm run build` and start the API. Docker builds the frontend and backend together.

## Set up integrations

All credentials are optional for browsing and running the API. The related feature returns a clear configuration error until credentials are set.

### TMDB

Set `TMDB_API_KEY` in `.env`. Sign in as an admin, open **Manage**, search TMDB, import a movie, then publish a screening. TMDB calls stay on the backend; its key is not sent to the browser.

Promote an existing local account from the project directory with `python scripts/promote_admin.py`. The script asks for the username and updates only that account.

### Razorpay test checkout and webhook

Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` from Razorpay test mode. This demo rejects a key that does not look like a test key. The browser checkout uses the public test key ID; the API secret stays on the backend.

Create a webhook pointing to `/api/payments/webhook` and subscribe to `payment.captured` and `payment.failed`. Copy the webhook's signing secret into `RAZORPAY_WEBHOOK_SECRET`. For local webhook delivery, expose the API with a temporary HTTPS tunnel and use that public URL as the callback. Do not use live keys for this demo.

Bookings hold inventory for `BOOKING_HOLD_MINUTES` (10 by default) while checkout is pending. A payment signature or verified captured-payment webhook confirms the booking. Webhook event IDs are recorded so retries are safe. Expired holds are released when that screening is next read or booked; this demo does not run a background worker.

### Google OAuth and Calendar

Create a Google OAuth **Web application** client, enable the Google Calendar API, and set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Add the exact `GOOGLE_REDIRECT_URI` (default `http://localhost:5173/oauth/callback`) to the OAuth client's authorized redirect URIs. Set `FRONTEND_URL` to the Vite origin (default `http://localhost:5173`). Add your account as a test user if Google's consent screen is in testing mode.

Users connect Calendar from **My tickets**. The app requests the Calendar events scope only when the user chooses to connect, stores the refresh token encrypted using `SECRET_KEY`, and offers an **Add to calendar** action for confirmed bookings. Changing `SECRET_KEY` makes previously stored Calendar tokens unreadable, so keep it stable for the local database.

## Booking and payment flow

- An admin imports movie metadata and publishes a dated screening with a capacity and price.
- A customer chooses a screening and ticket count. PostgreSQL row locks protect the screening inventory while the API creates a pending booking and a Razorpay order.
- The checkout callback signature is verified by the API. Razorpay's signed webhook is the retry-safe provider event path. Failed or expired holds return inventory to the screening.
- Confirmed bookings appear under **My tickets** and can be added to Google Calendar after authorization.
- Cancelling unpaid holds is supported. Refund processing for already paid bookings is outside this demo's scope.

## Main routes

- `GET /api/movies` and `GET /api/movies/{id}/screenings` browse films and upcoming screenings.
- `POST /api/movies/{id}/screenings` creates a screening (admin only).
- `GET /api/tmdb/search` and `POST /api/tmdb/import` search and import TMDB titles (import is admin only).
- `POST /api/bookings` reserves screening inventory and creates a payment order; send an `Idempotency-Key` header.
- `POST /api/payments/verify` verifies the browser checkout response; `POST /api/payments/webhook` receives signed provider events.
- `GET /api/calendar/connect`, `/callback`, and `/status` manage OAuth; `POST /api/calendar/bookings/{id}/event` creates a Calendar event for a confirmed booking.

## Verification

Run `python -m pytest` for API, integration-signature, migration, and booking regression checks. The PostgreSQL contention test runs only when `MOVIE_BOOKING_TEST_DB_URL` points at a disposable PostgreSQL test database. Do not point that variable at a database with data you need to keep.
