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
2. Install teh required dependencies:
```bash
   pip install -r requirements.txt
```
3. Start the FastAPI development server
   ```bash
   fastapi dev main.py
   ```
