# FastAPI Movie Booking System 

A full-stack movie booking system built with FastAPI, featuring role-based JWT Authentication and a server-rendered Jinja2 frontend.

## Features
* **Role-Based Access Control:** Only admins can add, edit, or delete movies. Regular users can browse and book tickets.
* **Booking Logic:** Users select the number of seats and showtime, and backend inventory math validates the transaction.
* **Security:** JWT authentication using HTTPOnly cookies to help protect authentication tokens from client-side JavaScript access. 
* **Data Validation:** Form inputs are strictly validated using Pydantic schemas.
* **Clean UI:** Server-rendered HTML utilizing Jinja2 templates and Bootstrap.
* **Database:** Relational SQLite database modeled with SQLAlchemy and cascading deletes.

## Tech Stack
* Python
* FastAPI
* SQLAlchemy & SQLite
* Jinja2
* Bootstrap

## Architecture

```text
Client
  |
  | HTTP
  v
FastAPI app
  |
  |-- Jinja2 templates render server-side HTML
  |-- JWT auth with HTTPOnly cookies protects user sessions
  |-- Role-based access controls admin-only movie management
  |
  v
SQLAlchemy ORM
  |
  v
PostgreSQL / Neon
```

### Booking Flow
User selects movie, showtime, and seats
  |
  v
FastAPI validates form input with Pydantic
  |
  v
Backend checks available seat inventory
  |
  |-- Enough seats: create booking and reduce available seats
  |-- Not enough seats: reject booking request
  |
  v
SQLAlchemy commits transaction to PostgreSQL


## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```
2. Create a `.env` file and add your `DATABASE_URL` and `SECRET_KEY`.
3. Install the required dependencies:
```bash
pip install -r requirements.txt
```
4. Run database migrations:
```bash
alembic upgrade head
```
5. Start the FastAPI development server:
```bash
fastapi dev main.py
```

## Production Deployment (Linux VPS)

This application is deployed on a Linux VPS using a traditional reverse-proxy architecture:

* **PostgreSQL (Neon):** Managed cloud database.
* **Alembic:** Used for schema migrations (solves the problem of `create_all` not being able to alter existing tables).
* **Gunicorn & Systemd:** Gunicorn acts as a process manager with Uvicorn workers. Systemd runs Gunicorn in the background 24/7 and restarts it automatically if it crashes or if the server reboots.
* **Nginx:** Acts as a reverse proxy. It listens on port 80 (HTTP) and forwards internet traffic to the local Gunicorn port (8000). It acts as a security buffer and load balancer so the FastAPI app isn't directly exposed to the raw internet.

## Dockerized Local Deployment

This application is containerized with Docker and can run locally against a managed PostgreSQL database such as Neon.

Docker: Packages the FastAPI app, Python runtime, and dependencies into a portable container.

PostgreSQL (Neon): Managed cloud database used as the production database.

Alembic: Handles schema migrations instead of relying on create_all, which cannot safely alter existing tables.

FastAPI Middleware: Adds application-level security headers to HTTP responses.

Build the Docker Image:

docker build -t fastapi-movie-booking .
Run the Container Locally:
docker run -p 8080:8080 --env-file .env fastapi-movie-booking

* **Cloud Run Deployment Target:**
The app is designed to be deployable to Google Cloud Run using the Dockerfile, but deployment requires an active Google Cloud billing account.
```bash
# 1. Log into your Google account in the terminal
gcloud auth login

# 2. Tell the CLI which project you are targeting
gcloud config set project <your-project-id>

# 3. Deploy the source code! (Google will use your Dockerfile to build and host the app)
gcloud run deploy fastapi-app --source . --region us-east1 --allow-unauthenticated
```


