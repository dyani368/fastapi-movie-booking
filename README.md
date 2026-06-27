# FastAPI Movie Booking System 

A full-stack movie booking system built with FastAPI, featuring role-based JWT Authentication and a server-rendered Jinja2 frontend.

## Features
* **Role-Based Access Control:** Only admins can add, edit, or delete movies. Regular users can browse and book tickets.
* **Booking Logic:** Users select the number of seats and showtime, and backend inventory math validates the transaction.
* **Security:** JWT Authentication with HTTPOnly cookies for maximum security against XSS attacks.
* **Data Validation:** Form inputs are strictly validated using Pydantic schemas.
* **Clean UI:** Server-rendered HTML utilizing Jinja2 templates and Bootstrap.
* **Database:** Relational SQLite database modeled with SQLAlchemy and cascading deletes.

## Tech Stack
* Python
* FastAPI
* SQLAlchemy & SQLite
* Jinja2
* Bootstrap

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

## Production Deployment Architecture

This application is deployed on a Linux VPS using a traditional reverse-proxy architecture:

* **PostgreSQL (Neon):** Managed cloud database.
* **Alembic:** Used for schema migrations (solves the problem of `create_all` not being able to alter existing tables).
* **Gunicorn & Systemd:** Gunicorn acts as a process manager with Uvicorn workers. Systemd runs Gunicorn in the background 24/7 and restarts it automatically if it crashes or if the server reboots.
* **Nginx:** Acts as a reverse proxy. It listens on port 80 (HTTP) and forwards internet traffic to the local Gunicorn port (8000). It acts as a security buffer and load balancer so the FastAPI app isn't directly exposed to the raw internet.
